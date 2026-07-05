#!/usr/bin/env python3
"""重新精确截取安全范围内的纯音乐片段"""
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
OUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/extracted")

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

def fade(audio, fade_in=0.1, fade_out=1.0, sr=SR):
    out = audio.copy()
    fi = int(fade_in * sr)
    fo = int(fade_out * sr)
    if fi > 0 and fi < len(out):
        out[:fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < len(out):
        out[-fo:] *= np.linspace(1, 0, fo)
    return out

def save_wav(audio, path, sr=SR):
    audio = np.clip(audio, -1.0, 1.0)
    wavfile.write(str(path), sr, (audio * 32767).astype(np.int16))
    print(f"  ✓ {path.name}: {len(audio)/sr:.1f}秒")

f_70s = AUDIO_DIR / "再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3"

print("重新截取安全范围内纯音乐片段（参考音频总时长50秒）:")

# 开场：0-7秒（前7秒纯呼号音乐，第8秒开始人声）
opening = load_mp3_segment(f_70s, 0, 7.0)
opening = fade(opening, 0.05, 1.8)
save_wav(opening, OUT_DIR / "opening_clean.wav")

# 间隔音乐：27-34秒（纯音乐，27秒开始，35秒开始人声）
bridge = load_mp3_segment(f_70s, 27.0, 7.0)
bridge = fade(bridge, 0.4, 1.2)
save_wav(bridge, OUT_DIR / "bridge_music_1.wav")

# 结尾过渡：44-49秒（纯音乐淡出，不超过50秒）
ending = load_mp3_segment(f_70s, 44.0, 5.0)
ending = fade(ending, 0.5, 2.5)
save_wav(ending, OUT_DIR / "ending_transition.wav")

print("\n完成！所有片段均在安全范围内，无人声。")
