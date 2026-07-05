#!/usr/bin/env python3
"""
分析参考音频的特征参数
提取频谱、频响、底噪、动态范围等信息
"""

import os
import sys
import numpy as np
from scipy.io import wavfile
from scipy.signal import welch, spectrogram
import subprocess
import json
import tempfile

AUDIO_DIR = "/Users/swan/Documents/1024/vibe/时光收音机/audio fyi"
FFMPEG = "/Users/swan/Library/Python/3.9/lib/python/site-packages/imageio_ffmpeg/binaries/ffmpeg-macos-aarch64-v7.1"

FILES = [
    "1984.mp3",
    "1986 年.mp3",
    "再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3",
    "年代广播参考.mp3",
]

def convert_to_wav(mp3_path, wav_path, sr=24000):
    """将 mp3 转换为单声道 wav"""
    cmd = [
        FFMPEG, "-y", "-i", mp3_path,
        "-ac", "1", "-ar", str(sr),
        wav_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

def analyze_audio(wav_path, label=""):
    """分析音频特征"""
    sr, audio = wavfile.read(wav_path)
    if audio.dtype == np.int16:
        audio = audio.astype(np.float64) / 32768.0
    elif audio.dtype == np.int32:
        audio = audio.astype(np.float64) / 2147483648.0

    duration = len(audio) / sr

    # 基本统计
    rms = np.sqrt(np.mean(audio**2))
    peak = np.max(np.abs(audio))
    dynamic_range = 20 * np.log10(peak / (rms + 1e-10))

    # 频谱分析（使用 Welch 方法）
    freqs, psd = welch(audio, sr, nperseg=4096)
    psd_db = 10 * np.log10(psd + 1e-20)

    # 找到有效频带范围（-20dB 带宽）
    max_psd = np.max(psd_db)
    threshold = max_psd - 20
    above_threshold = freqs[psd_db > threshold]
    if len(above_threshold) > 0:
        freq_low = above_threshold[0]
        freq_high = above_threshold[-1]
    else:
        freq_low = 0
        freq_high = sr / 2

    # 能量频段分布
    bands = {
        "低频(0-300Hz)": (0, 300),
        "低中频(300-1000Hz)": (300, 1000),
        "中频(1000-3000Hz)": (1000, 3000),
        "中高频(3000-5000Hz)": (3000, 5000),
        "高频(5000Hz+)": (5000, sr//2),
    }

    band_energies = {}
    total_energy = np.sum(psd)
    for band_name, (f_low, f_high) in bands.items():
        mask = (freqs >= f_low) & (freqs < f_high)
        band_energy = np.sum(psd[mask])
        band_energies[band_name] = band_energy / (total_energy + 1e-20) * 100

    # 底噪估计（取静音段的能量）
    # 简单方法：取能量最低的 10% 帧作为底噪估计
    frame_size = int(sr * 0.05)  # 50ms 帧
    n_frames = len(audio) // frame_size
    if n_frames > 10:
        frame_energies = []
        for i in range(n_frames):
            frame = audio[i*frame_size:(i+1)*frame_size]
            frame_energies.append(np.sqrt(np.mean(frame**2)))
        frame_energies = np.array(frame_energies)
        noise_floor = np.percentile(frame_energies, 10)
        noise_ratio = noise_floor / (rms + 1e-10)
    else:
        noise_floor = 0
        noise_ratio = 0

    # 零交叉率（估计语音/音乐特征）
    zcr = np.mean(np.abs(np.diff(np.sign(audio)))) / 2

    return {
        "label": label,
        "duration_sec": round(duration, 1),
        "sample_rate": sr,
        "rms": round(float(rms), 4),
        "peak": round(float(peak), 4),
        "dynamic_range_db": round(float(dynamic_range), 1),
        "freq_low_hz": round(float(freq_low), 0),
        "freq_high_hz": round(float(freq_high), 0),
        "bandwidth_hz": round(float(freq_high - freq_low), 0),
        "noise_floor_ratio": round(float(noise_ratio), 4),
        "zcr": round(float(zcr), 4),
        "band_energies_pct": {k: round(v, 1) for k, v in band_energies.items()},
    }

def main():
    results = []
    temp_dir = tempfile.mkdtemp()

    for f in FILES:
        mp3_path = os.path.join(AUDIO_DIR, f)
        if not os.path.exists(mp3_path):
            print(f"⚠️ 文件不存在: {f}")
            continue

        wav_path = os.path.join(temp_dir, f.replace(".mp3", ".wav").replace(" ", "_"))

        print(f"📊 正在分析: {f}")
        print(f"   转换为 WAV...")
        if convert_to_wav(mp3_path, wav_path):
            result = analyze_audio(wav_path, label=f)
            results.append(result)
            print(f"   ✅ 分析完成")
        else:
            print(f"   ❌ 转换失败")

    # 输出结果
    print("\n" + "="*80)
    print("参考音频特征分析报告")
    print("="*80)

    for r in results:
        print(f"\n📻 {r['label']}")
        print(f"   时长: {r['duration_sec']}秒")
        print(f"   采样率: {r['sample_rate']}Hz")
        print(f"   RMS能量: {r['rms']}")
        print(f"   峰值: {r['peak']}")
        print(f"   动态范围: {r['dynamic_range_db']}dB")
        print(f"   有效频带: {r['freq_low_hz']}Hz - {r['freq_high_hz']}Hz (带宽 {r['bandwidth_hz']}Hz)")
        print(f"   底噪比: {r['noise_floor_ratio']*100:.1f}%")
        print(f"   零交叉率: {r['zcr']}")
        print(f"   频段能量分布:")
        for band, pct in r['band_energies_pct'].items():
            bar = "█" * int(pct / 2)
            print(f"     {band:20s}: {pct:5.1f}% {bar}")

    # 保存为 JSON
    output_path = "/Users/swan/Documents/1024/vibe/时光收音机/docs/tech/reference-audio-analysis.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📄 结果已保存到: {output_path}")

    # 清理临时文件
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
