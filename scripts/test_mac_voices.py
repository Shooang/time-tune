#!/usr/bin/env python3
"""测试macOS所有中文音色，找最接近年代播音员的"""
import subprocess
from pathlib import Path
import shutil

# 找ffmpeg
FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    FFMPEG = shutil.which("ffmpeg")

OUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/output/voice_compare_mac")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_TEXT = "中央人民广播电台。中央人民广播电台。各位听众同志们，早上好。今天是一九七零年四月二十六日，现在是新闻和报纸摘要节目时间。首先报告国内要闻。我国第一颗人造地球卫星东方红一号发射成功。"

# 获取所有中文音色
result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
all_voices = result.stdout.splitlines()

zh_voices = []
for line in all_voices:
    if "zh_CN" in line or "zh-TW" in line or "zh-HK" in line or "Chinese" in line:
        name = line.split()[0]
        zh_voices.append(name)

print(f"找到 {len(zh_voices)} 个中文音色:\n")
for v in zh_voices:
    print(f"  - {v}")

# 再额外加几个声音浑厚的男声
extra_male = ["Eddy", "Grandpa", "Reed", "Rocko", "Alex", "Daniel", "Tom", "Fred"]
all_test = list(dict.fromkeys(zh_voices + extra_male))

print(f"\n🔊 测试 {len(all_test)} 个音色，语速220字/分钟...")

for voice_name in all_test:
    safe_name = voice_name.replace(" ", "_")
    out_aiff = OUT_DIR / f"{safe_name}.aiff"
    out_wav = OUT_DIR / f"{safe_name}.wav"
    if out_wav.exists():
        print(f"  已存在: {voice_name}")
        continue
    print(f"  测试: {voice_name}...", end=" ", flush=True)
    try:
        subprocess.run([
            "say", "-v", voice_name, "-r", "220",
            "-o", str(out_aiff), TEST_TEXT
        ], capture_output=True, timeout=30)
        # 转wav
        if FFMPEG:
            subprocess.run([
                FFMPEG, "-y", "-i", str(out_aiff),
                "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                str(out_wav)
            ], capture_output=True, timeout=30)
            out_aiff.unlink()
            print("✓")
        else:
            print("✓ (aiff)")
    except Exception as e:
        print(f"✗ {e}")

print(f"\n✅ 测试音频保存在: {OUT_DIR}")
print("\n重点试听:")
print("  - Eddy: 中文男声，最接近新闻播音风格")
print("  - Grandpa: 老年男声，可能有年代感")
print("  - Reed: 男声，声音偏厚")
print("  - Tingting: 女声（作为对比）")
print("请试听后告诉我哪个最接近参考音频的播音员音色")
