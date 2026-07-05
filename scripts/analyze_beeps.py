#!/usr/bin/env python3
"""
分析extracted目录下所有音乐片段，找出哪些包含"滴滴滴"报时声
"""
import numpy as np
from scipy.io import wavfile
from pathlib import Path

EXTRACTED_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/extracted")
SONGS_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/bgm/songs")

SR = 22050

def analyze_wav(path):
    sr, data = wavfile.read(str(path))
    data = data.astype(np.float32) / 32768.0
    if len(data.shape) > 1:
        data = data[:, 0]
    dur = len(data) / sr

    # 逐秒分析
    print(f"\n📊 {path.name} ({dur:.1f}秒)")
    for s in range(0, int(dur)):
        chunk = data[s*sr:(s+1)*sr]
        if len(chunk) < sr * 0.5:
            continue
        rms = np.sqrt(np.mean(chunk**2))
        # 检测"滴滴滴"特征：高频脉冲 + 低频静默交替
        fft = np.abs(np.fft.rfft(chunk))
        freq = np.fft.rfftfreq(len(chunk), 1/sr)
        # 1000-2000Hz区域的窄带能量（报时滴声的特征）
        beep_band = np.sum(fft[(freq > 800) & (freq < 2000)])
        total_energy = np.sum(fft) + 1e-10
        beep_ratio = beep_band / total_energy

        # 检测脉冲性（短时能量变化大 = 滴滴声）
        win = sr // 10  # 100ms窗口
        energies = [np.sqrt(np.mean(chunk[i:i+win]**2)) for i in range(0, len(chunk)-win, win)]
        if len(energies) > 1:
            energy_var = np.std(energies) / (np.mean(energies) + 1e-10)
        else:
            energy_var = 0

        is_beep = beep_ratio > 0.3 and energy_var > 0.5
        is_speech = rms > 0.03 and beep_ratio < 0.25 and energy_var < 0.8
        is_music = beep_ratio > 0.15 and energy_var < 0.4

        status = "🔔" if is_beep else ("🗣️" if is_speech else ("🎵" if is_music else "  "))
        flag = " ⚠️ 滴滴声!" if is_beep else ""
        print(f"  {s:02d}s {status} RMS={rms:.3f} beep={beep_ratio:.2f} var={energy_var:.2f}{flag}")

print("=" * 60)
print("🔍 分析extracted目录音乐片段")
print("=" * 60)

for f in sorted(EXTRACTED_DIR.glob("*.wav")):
    analyze_wav(f)

print("\n" + "=" * 60)
print("🎵 分析songs目录歌曲（仅前5秒）")
print("=" * 60)

# 分析歌曲前5秒
import subprocess, tempfile
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    import shutil
    FFMPEG = shutil.which("ffmpeg")

for f in sorted(SONGS_DIR.glob("*.mp3")):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = Path(tmp.name)
    subprocess.run([FFMPEG, "-y", "-t", "5", "-i", str(f), "-ac", "1", "-ar", str(SR),
                    "-acodec", "pcm_s16le", str(tmp_path)], capture_output=True, timeout=30)
    analyze_wav(tmp_path)
    tmp_path.unlink()
