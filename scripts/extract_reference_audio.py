#!/usr/bin/env python3
"""
从参考音频中截取开场曲/间隔音乐片段
通过检测音乐段（高能量、宽频带持续段）和人声段，自动分割提取
"""

import os
import sys
import json
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile

FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if result.returncode == 0:
        FFMPEG = "ffmpeg"

AUDIO_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio fyi")
OUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/extracted")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SR = 22050


def load_mp3(path, sr=SR):
    """加载mp3为numpy数组"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-i", str(path), "-ac", "1", "-ar", str(sr),
           "-acodec", "pcm_s16le", str(wav_path)]
    subprocess.run(cmd, capture_output=True, timeout=60)
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0, sr_out


def detect_segments(audio, sr, frame_ms=30, hop_ms=10):
    """
    检测音频中的人声段/音乐段/静音段
    返回: [(start_sec, end_sec, type), ...]
    type: 'music'（音乐，宽频带、持续能量）、'voice'（人声，窄带、有共振峰）、'silence'
    """
    frame_size = int(sr * frame_ms / 1000)
    hop_size = int(sr * hop_ms / 1000)

    features = []
    for i in range(0, len(audio) - frame_size, hop_size):
        frame = audio[i:i+frame_size]
        if len(frame) < frame_size:
            break

        energy = np.sqrt(np.mean(frame**2))

        # FFT分析频带分布
        fft = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
        freqs = np.fft.rfftfreq(len(frame), 1/sr)

        # 低/中/高频能量比
        low = np.sum(fft[freqs < 800])
        mid = np.sum(fft[(freqs >= 800) & (freqs < 3000)])
        high = np.sum(fft[freqs >= 3000])
        total = low + mid + high + 1e-10

        # 频谱质心
        if np.sum(fft) > 0:
            centroid = np.sum(freqs * fft) / np.sum(fft)
        else:
            centroid = 0

        # 零交叉率
        zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2

        features.append({
            'energy': energy,
            'centroid': centroid,
            'low_ratio': low/total,
            'mid_ratio': mid/total,
            'high_ratio': high/total,
            'zcr': zcr,
            'time': i / sr,
        })

    # VAD: 基于能量的有声/无声
    energies = np.array([f['energy'] for f in features])
    centroids = np.array([f['centroid'] for f in features])

    threshold = np.percentile(energies[energies > 0], 10) * 1.5
    voiced = energies > threshold

    # 分类：音乐 vs 人声
    # 音乐特征：高频能量更高、频谱质心更高、更稳定
    # 人声特征：主要能量在300-3000Hz、质心较低、变化快
    segments = []
    in_seg = False
    seg_start = 0
    seg_type = ''

    min_seg_frames = int(500 / hop_ms)  # 最短0.5秒

    for i in range(len(features)):
        is_voiced = voiced[i] if i < len(voiced) else False
        centroid = centroids[i] if i < len(centroids) else 0

        if is_voiced:
            if centroid > 1500 and features[i]['high_ratio'] > 0.15:
                cur_type = 'music'
            else:
                cur_type = 'voice'
        else:
            cur_type = 'silence'

        if not in_seg and cur_type != 'silence':
            in_seg = True
            seg_start = features[i]['time']
            seg_type = cur_type
        elif in_seg:
            if cur_type != seg_type and cur_type != 'silence':
                # 类型变了，但如果太短不算，平滑一下
                seg_end = features[i]['time']
                if seg_end - seg_start > 0.5:
                    segments.append((seg_start, seg_end, seg_type))
                seg_start = features[i]['time']
                seg_type = cur_type
            elif cur_type == 'silence':
                seg_end = features[i]['time']
                if seg_end - seg_start > 0.3:
                    segments.append((seg_start, seg_end, seg_type))
                    in_seg = False

    if in_seg:
        segments.append((seg_start, len(audio)/sr, seg_type))

    # 合并相邻同类片段
    merged = []
    for seg in segments:
        if merged and merged[-1][2] == seg[2] and seg[0] - merged[-1][1] < 0.5:
            merged[-1] = (merged[-1][0], seg[1], seg[2])
        else:
            merged.append(seg)

    return merged


def extract_segment(audio, sr, start, end, fade_in=0.2, fade_out=0.5):
    """截取音频片段并添加淡入淡出"""
    s = int(start * sr)
    e = int(end * sr)
    chunk = audio[s:e].copy()

    fi = int(fade_in * sr)
    fo = int(fade_out * sr)
    if fi < len(chunk):
        chunk[:fi] *= np.linspace(0, 1, fi)
    if fo < len(chunk):
        chunk[-fo:] *= np.linspace(1, 0, fo)
    return chunk


def save_wav(audio, path, sr=SR):
    audio = np.clip(audio, -1.0, 1.0)
    wavfile.write(str(path), sr, (audio * 32767).astype(np.int16))
    dur = len(audio)/sr
    print(f"  ✓ 保存: {path.name} ({dur:.1f}秒)")


# 参考音频文件
FILES = [
    ("再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3", "70年代中央台新闻和报纸摘要"),
    ("1984.mp3", "1984年广播"),
    ("年代广播参考.mp3", "年代广播综合参考"),
]

print("=" * 60)
print("🎵 从参考音频中提取音乐片段")
print("=" * 60)

all_segments = {}

for filename, label in FILES:
    mp3_path = AUDIO_DIR / filename
    if not mp3_path.exists():
        print(f"⚠️ 文件不存在: {filename}")
        continue

    print(f"\n📂 分析: {label}")
    audio, sr = load_mp3(mp3_path)
    print(f"   时长: {len(audio)/sr:.1f}秒")

    segs = detect_segments(audio, sr)

    # 打印前20个片段
    music_segs = [s for s in segs if s[2] == 'music']
    voice_segs = [s for s in segs if s[2] == 'voice']
    print(f"   检测到 {len(music_segs)} 个音乐段, {len(voice_segs)} 个人声段")

    for i, (start, end, stype) in enumerate(segs[:30]):
        dur = end - start
        icon = "🎵" if stype == "music" else "🎤"
        print(f"   {icon} [{stype:5s}] {start:6.1f}s - {end:6.1f}s ({dur:.1f}s)")

    all_segments[label] = (audio, segs)


# 从70年代新闻节目中提取开场呼号
print("\n" + "=" * 60)
print("🔍 提取关键音乐片段...")

target_label = "70年代中央台新闻和报纸摘要"
if target_label in all_segments:
    audio, segs = all_segments[target_label]

    # 找第一个音乐段（开场曲）
    music_segs = [(s, e) for s, e, t in segs if t == 'music']

    if music_segs:
        # 第一个音乐段就是开场曲
        first_s, first_e = music_segs[0]
        print(f"\n🎺 开场曲（第一个音乐段）: {first_s:.1f}s - {first_e:.1f}s")

        # 截取开场曲（取前8秒左右）
        opening_end = min(first_e, first_s + 10)
        opening_chunk = extract_segment(audio, SR, first_s, opening_end, 0.1, 1.5)
        save_wav(opening_chunk, OUT_DIR / "opening_ref_70s.wav")
        start_time, end_time = first_s, opening_end

        # 找间隔音乐：人声之间的短音乐段（2-6秒）
        bridges = []
        for s, e, t in segs:
            if t == 'music' and 1.5 < (e-s) < 8:
                bridges.append((s, e))

        print(f"\n🔔 间隔提示音候选（2-6秒音乐段）:")
        for i, (s, e) in enumerate(bridges[:5]):
            print(f"   [{i}] {s:.1f}s - {e:.1f}s ({e-s:.1f}s)")
            chunk = extract_segment(audio, SR, s, e, 0.1, 0.5)
            save_wav(chunk, OUT_DIR / f"bridge_ref_{i}.wav")
            start_time, end_time = s, e

        # 找结束音乐（最后一个音乐段）
        if len(music_segs) >= 2:
            last_s, last_e = music_segs[-1]
            print(f"\n🎶 结束曲（最后音乐段）: {last_s:.1f}s - {last_e:.1f}s")
            closing_chunk = extract_segment(audio, SR, last_s, min(last_e, last_s+15), 0.5, 2.0)
            save_wav(closing_chunk, OUT_DIR / "closing_ref.wav")
            start_time, end_time = last_s, min(last_e, last_s+15)

# 从1984年音频也提取一些音乐片段
target_label2 = "1984年广播"
if target_label2 in all_segments:
    audio, segs = all_segments[target_label2]
    music_segs = [(s, e) for s, e, t in segs if t == 'music']

    if music_segs:
        print(f"\n📻 1984年广播音乐段:")
        first_s, first_e = music_segs[0]
        print(f"   开场: {first_s:.1f}s - {first_e:.1f}s")
        opening_chunk = extract_segment(audio, SR, first_s, min(first_e, first_s+10), 0.1, 1.5)
        save_wav(opening_chunk, OUT_DIR / "opening_ref_80s.wav")
        start_time, end_time = first_s, min(first_e, first_s+10)

print("\n" + "=" * 60)
print(f"✅ 提取完成！文件保存在: {OUT_DIR}")
print("=" * 60)
