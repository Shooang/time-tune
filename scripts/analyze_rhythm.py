#!/usr/bin/env python3
"""
分析参考音频的节奏模式：
1. 检测人声段/音乐段/静音段
2. 测量语速（字/分钟）
3. 统计人声和音乐的交替模式
"""

import os
import sys
import json
import subprocess
import tempfile
import numpy as np
from scipy.io import wavfile
from pathlib import Path

FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if result.returncode == 0:
        FFMPEG = "ffmpeg"

AUDIO_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio fyi")
OUTPUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/docs/tech")

FILES = [
    ("1984.mp3", "1984年广播"),
    ("1986 年.mp3", "1986年广播片段"),
    ("再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3", "70年代中央台新闻和报纸摘要"),
    ("年代广播参考.mp3", "年代广播综合参考"),
]

def convert_to_wav(mp3_path, wav_path, sr=16000):
    cmd = [FFMPEG, "-y", "-i", str(mp3_path), "-ac", "1", "-ar", str(sr), str(wav_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return result.returncode == 0

def analyze_rhythm(wav_path, label=""):
    sr, audio = wavfile.read(wav_path)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float32) / 32768.0

    duration = len(audio) / sr
    print(f"\n📻 分析: {label}")
    print(f"   时长: {duration:.1f}秒 ({duration/60:.1f}分钟)")
    print(f"   采样率: {sr}Hz")

    # 分帧分析 (每帧25ms, 步长10ms)
    frame_size = int(sr * 0.025)
    hop_size = int(sr * 0.010)

    energies = []
    zcrs = []
    spec_centroids = []

    for i in range(0, len(audio) - frame_size, hop_size):
        frame = audio[i:i+frame_size]
        energy = np.sqrt(np.mean(frame**2))
        zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2

        # 频谱质心（区分人声和音乐）
        fft = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        freqs = np.fft.rfftfreq(len(frame), 1/sr)
        if np.sum(fft) > 0:
            centroid = np.sum(freqs * fft) / np.sum(fft)
        else:
            centroid = 0

        energies.append(energy)
        zcrs.append(zcr)
        spec_centroids.append(centroid)

    energies = np.array(energies)
    zcrs = np.array(zcrs)
    spec_centroids = np.array(spec_centroids)

    # 归一化能量
    energy_norm = energies / (np.max(energies) + 1e-10)

    # VAD: 能量超过阈值的部分认为是有声段
    threshold = np.percentile(energy_norm, 15) + 0.05
    voice_segments = []
    in_voice = False
    start = 0

    for i in range(len(energy_norm)):
        is_voice = energy_norm[i] > threshold

        if is_voice and not in_voice:
            start = i
            in_voice = True
        elif not is_voice and in_voice:
            if (i - start) * 0.010 > 0.3:  # 最短300ms
                voice_segments.append((start * 0.010, i * 0.010))
            in_voice = False

    if in_voice:
        voice_segments.append((start * 0.010, len(energy_norm) * 0.010))

    # 合并相邻的语音段（间隔<500ms的合并）
    merged = []
    for seg in voice_segments:
        if merged and seg[0] - merged[-1][1] < 0.5:
            merged[-1] = (merged[-1][0], seg[1])
        else:
            merged.append(seg)
    voice_segments = merged

    # 统计
    total_voice = sum(end - start for start, end in voice_segments)
    total_silence = duration - total_voice

    # 计算平均语音段长度和间隔
    voice_durations = [end - start for start, end in voice_segments]
    silence_durations = []
    for i in range(len(voice_segments) - 1):
        silence_durations.append(voice_segments[i+1][0] - voice_segments[i][1])

    print(f"\n   📊 语音段统计:")
    print(f"   语音段数量: {len(voice_segments)}")
    print(f"   总语音时长: {total_voice:.1f}秒 ({total_voice/duration*100:.1f}%)")
    print(f"   总静音/音乐时长: {total_silence:.1f}秒 ({total_silence/duration*100:.1f}%)")

    if voice_durations:
        print(f"   平均语音段时长: {np.mean(voice_durations):.1f}秒")
        print(f"   语音段时长范围: {min(voice_durations):.1f}s - {max(voice_durations):.1f}s")
    if silence_durations:
        print(f"   平均间隔时长: {np.mean(silence_durations):.1f}秒")
        print(f"   间隔时长范围: {min(silence_durations):.1f}s - {max(silence_durations):.1f}s")

    # 频谱质心分析（人声vs音乐）
    # 人声的频谱质心通常在 500-1500Hz，音乐/噪声可能不同
    voice_centroids = []
    non_voice_centroids = []

    for i in range(len(energy_norm)):
        t = i * 0.010
        is_voice = any(start <= t <= end for start, end in voice_segments)
        if is_voice:
            voice_centroids.append(spec_centroids[i])
        elif energy_norm[i] > 0.01:
            non_voice_centroids.append(spec_centroids[i])

    if voice_centroids:
        print(f"\n   🎵 频谱特征:")
        print(f"   语音段平均频谱质心: {np.mean(voice_centroids):.0f}Hz")
    if non_voice_centroids:
        print(f"   非语音段(音乐/噪声)平均频谱质心: {np.mean(non_voice_centroids):.0f}Hz")

    # 语速估计：通过零交叉率和能量变化估计音节率
    # 中文字语大约3-5字/秒，播音约4-6字/秒
    # 用能量包络的峰值来估计音节数
    from scipy.signal import find_peaks
    if total_voice > 0:
        voice_audio = np.concatenate([
            audio[int(start*sr):int(end*sr)]
            for start, end in voice_segments
            if int(end*sr) <= len(audio)
        ])
        if len(voice_audio) > sr:
            env = np.abs(voice_audio)
            # 简单低通滤波获取包络
            win = int(sr * 0.02)
            env_smooth = np.convolve(env, np.ones(win)/win, mode='same')
            peaks, _ = find_peaks(env_smooth, distance=int(sr*0.15), height=np.mean(env_smooth)*0.5)
            syllable_rate = len(peaks) / (len(voice_audio)/sr)
            # 中文字 ≈ 1.5-2 个音节峰
            est_wpm = syllable_rate / 1.5 * 60  # 字/分钟
            print(f"\n   🗣️ 语速估计:")
            print(f"   音节率: {syllable_rate:.1f} 音节/秒")
            print(f"   估计语速: {est_wpm:.0f} 字/分钟")

    return {
        "label": label,
        "duration_sec": round(duration, 1),
        "num_voice_segments": len(voice_segments),
        "total_voice_sec": round(total_voice, 1),
        "voice_pct": round(total_voice/duration*100, 1),
        "avg_voice_segment_sec": round(float(np.mean(voice_durations)), 1) if voice_durations else 0,
        "avg_gap_sec": round(float(np.mean(silence_durations)), 1) if silence_durations else 0,
        "voice_centroid_hz": round(float(np.mean(voice_centroids)), 0) if voice_centroids else 0,
        "voice_segments": [(round(s,1), round(e,1)) for s, e in voice_segments[:20]],  # 前20段
    }

def main():
    if not FFMPEG:
        print("❌ FFmpeg 不可用")
        return

    results = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for filename, label in FILES:
            mp3_path = AUDIO_DIR / filename
            if not mp3_path.exists():
                print(f"⚠️ 文件不存在: {filename}")
                continue

            wav_path = tmp / f"{label}.wav"
            print(f"📂 转换: {filename}")
            if convert_to_wav(mp3_path, wav_path):
                result = analyze_rhythm(wav_path, label)
                if result:
                    results.append(result)

    # 保存结果
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "reference-audio-rhythm.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📄 结果已保存: {output_path}")

if __name__ == "__main__":
    main()
