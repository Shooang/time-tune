#!/usr/bin/env python3
"""检查截取的音乐片段内容，找出哪些位置有人声"""
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
    import shutil
    FFMPEG = shutil.which("ffmpeg")

AUDIO_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio fyi")
EXTRACTED_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/extracted")
SR = 22050

def load_mp3_segment(path, start, duration, sr=SR):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-ss", str(start), "-t", str(duration),
           "-i", str(path), "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav_path)]
    subprocess.run(cmd, capture_output=True, timeout=60)
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0

print("=" * 60)
print("🔍 分析参考音频40-80秒区域（寻找报时/人声位置）")
print("=" * 60)

f_70s = AUDIO_DIR / "再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3"
full = load_mp3_segment(f_70s, 0, 130)

win = SR
for s in range(40, 130, 2):
    chunk = full[s*win:(s+2)*win]
    if len(chunk) < win:
        continue
    rms = np.sqrt(np.mean(chunk**2))
    fft = np.abs(np.fft.rfft(chunk))
    freq = np.fft.rfftfreq(len(chunk), 1/SR)
    high_energy = np.sum(fft[freq > 1800]) / (np.sum(fft) + 1e-10)
    zcr = np.sum(np.abs(np.diff(np.sign(chunk)))) / (2 * len(chunk))

    # 检测人声特征：中低频为主，zcr较低
    is_speech = rms > 0.03 and high_energy < 0.2
    is_music = high_energy > 0.15 and rms > 0.05
    status = "🗣️" if is_speech else ("🎵" if is_music else "  ")
    bar = "█" * int(rms * 70)
    print(f"  {s:03d}-{s+2:03d}s {status} RMS={rms:.3f} high={high_energy:.2f} {bar[:35]}")
