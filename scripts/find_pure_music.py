#!/usr/bin/env python3
"""
精确分析70年代新闻节目音频，逐段检测纯音乐位置
"""
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
OUT_DIR.mkdir(parents=True, exist_ok=True)

SR = 22050
f_70s = AUDIO_DIR / "再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3"


def load_mp3_segment(path, start, duration, sr=SR):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-ss", str(start), "-t", str(duration),
           "-i", str(path), "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav_path)]
    subprocess.run(cmd, capture_output=True, timeout=60)
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0


def fade(audio, fade_in=0.1, fade_out=0.8, sr=SR):
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


print("=" * 60)
print("🔍 逐秒分析70年代新闻音频，寻找纯音乐片段")
print("=" * 60)

# 先加载完整音频前60秒
print("\n📊 逐秒能量分析（0-60秒）:")
full_audio = load_mp3_segment(f_70s, 0, 65)
win_len = SR  # 1秒窗口
music_segments = []

for s in range(0, 65):
    chunk = full_audio[s*win_len:(s+1)*win_len]
    if len(chunk) < win_len * 0.5:
        continue
    rms = np.sqrt(np.mean(chunk**2))
    # 检测音乐特征：高频能量占比（音乐高频比人声丰富）
    fft = np.abs(np.fft.rfft(chunk))
    freq = np.fft.rfftfreq(len(chunk), 1/SR)
    # 2000Hz以上能量占比
    high_energy = np.sum(fft[freq > 2000]) / (np.sum(fft) + 1e-10)
    # 零交叉率（音乐通常比连续人声低一些，但铜管乐器较高）
    zcr = np.sum(np.abs(np.diff(np.sign(chunk)))) / (2 * len(chunk))

    is_music = high_energy > 0.15 and rms > 0.05
    is_speech = rms > 0.03 and high_energy < 0.25

    status = "🎵" if is_music else ("🗣️" if is_speech else "  ")
    bar = "█" * int(rms * 80)
    print(f"  {s:02d}s {status} RMS={rms:.3f} high={high_energy:.2f} zcr={zcr:.3f} {bar[:40]}")

print("\n" + "=" * 60)
print("✂️  截取关键音乐片段")
print("=" * 60)

# 根据用户提到的时间点截取：
# 1. 开场呼号：0-8秒（前4秒OK）
# 2. 19-25秒（第一个BRIDGE位置）
# 3. 58-64秒（第二个BRIDGE位置）

# 先让我们看看实际的人声/音乐分布，从上面输出找纯音乐段
# 手动检查几个候选区域
candidates = [
    # 开场呼号：0-8秒
    ("opening_fanfare_v2", 0, 8.0),
    # 试截取18-27秒（第一个间隔，对应19-25s）
    ("bridge_1_18_27", 18.0, 9.0),
    # 试截取55-66秒（第二个间隔，对应58-64s）
    ("bridge_2_55_66", 55.0, 11.0),
    # 检查结尾有没有完整音乐
    ("ending_candidate", 100, 30),
]

for name, start, dur in candidates:
    try:
        seg = load_mp3_segment(f_70s, start, dur)
        seg = fade(seg, 0.1, 0.8)
        save_wav(seg, OUT_DIR / f"{name}.wav")
        print(f"  ✓ {name}: {start}s - {start+dur}s")
    except Exception as e:
        print(f"  ✗ {name} 失败: {e}")

print(f"\n✅ 片段保存到: {OUT_DIR}")
print("\n请试听 opening_fanfare_v2, bridge_1_18_27, bridge_2_55_66 确认哪些是纯音乐")
