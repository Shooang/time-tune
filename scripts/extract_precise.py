#!/usr/bin/env python3
"""
手动精确截取参考音频片段
根据自动分析结果，精确截取：
- 70年代新闻节目：
  - 开场呼号：0-8秒（包含前8秒的呼号音乐）
  - 间隔音乐：27-35秒
- 年代广播参考（长音频）：找更长的开场和间隔音乐
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


def load_mp3(path, sr=SR, start=0, duration=None):
    """加载mp3为numpy数组，支持指定起始和时长"""
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-i", str(path), "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav_path)]
    subprocess.run(cmd, capture_output=True, timeout=60)
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0, sr_out


def fade(audio, fade_in=0.2, fade_out=0.8, sr=SR):
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


print("=" * 60)
print("🎵 精确截取参考音频音乐片段")
print("=" * 60)

# 1. 70年代中央台新闻节目
f_70s = AUDIO_DIR / "再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3"
print(f"\n📻 处理: 70年代中央台新闻和报纸摘要")

# 截取开场0-8秒
opening_70s, _ = load_mp3(f_70s, start=0, duration=8.5)
opening_70s = fade(opening_70s, 0.05, 1.5)
save_wav(opening_70s, OUT_DIR / "opening_70s_exact.wav")

# 截取间隔音乐27-35秒
bridge_70s, _ = load_mp3(f_70s, start=27.0, duration=8.5)
bridge_70s = fade(bridge_70s, 0.1, 0.8)
save_wav(bridge_70s, OUT_DIR / "bridge_70s_exact.wav")

# 2. 年代广播参考（长音频，找完整音乐段）
f_ref = AUDIO_DIR / "年代广播参考.mp3"
print(f"\n📻 处理: 年代广播参考（长音频）")

# 根据之前的检测结果，找音乐段
# 先检查前150秒内的音乐段，手动截取几个候选
# 基于分析结果: 58-60, 62-63, 70-72, 75-77, 78-80, 80-83, 84-86, 90-136是长段人声
# 让我们截取几个可能的音乐段

# 检查0-15秒（开场）
opening_ref, _ = load_mp3(f_ref, start=0, duration=15)
opening_ref = fade(opening_ref, 0.05, 1.5)
save_wav(opening_ref, OUT_DIR / "opening_ref_candidate_0_15.wav")

# 截取人声后的间隔段
# 90秒开始是长段人声到136秒，之后应该有音乐
bridge_ref_1, _ = load_mp3(f_ref, start=135.5, duration=10)
bridge_ref_1 = fade(bridge_ref_1, 0.1, 1.0)
save_wav(bridge_ref_1, OUT_DIR / "bridge_ref_candidate_135.wav")

# 看55-65秒区域
seg_55, _ = load_mp3(f_ref, start=55, duration=15)
seg_55 = fade(seg_55, 0.1, 0.5)
save_wav(seg_55, OUT_DIR / "seg_ref_55_70.wav")

# 看70-90秒区域
seg_70, _ = load_mp3(f_ref, start=70, duration=22)
seg_70 = fade(seg_70, 0.1, 0.5)
save_wav(seg_70, OUT_DIR / "seg_ref_70_92.wav")

# 3. 1984年广播
f_84 = AUDIO_DIR / "1984.mp3"
print(f"\n📻 处理: 1984年广播")
opening_84, _ = load_mp3(f_84, start=0, duration=15)
opening_84 = fade(opening_84, 0.05, 1.5)
save_wav(opening_84, OUT_DIR / "opening_1984_0_15.wav")

print(f"\n✅ 候选片段已保存到: {OUT_DIR}")
print("   请人工试听后选择最好的片段重命名使用")
