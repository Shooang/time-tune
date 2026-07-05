#!/usr/bin/env python3
"""
批量生成1949-1960年月度生活片段TTS音频，带年代感后处理。
使用 edge-tts 生成语音，添加50年代老式广播效果。
"""
import asyncio
import json
import os
import sys
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "life-snippets.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "life-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.88


def bandpass_filter(audio, sr, low, high):
    from scipy.signal import butter, lfilter
    nyq = 0.5 * sr
    lo = max(0.001, low / nyq)
    hi = min(0.999, high / nyq)
    if lo >= hi:
        return audio
    b, a = butter(4, [lo, hi], btype='band')
    return lfilter(b, a, audio)


def add_distortion(audio, drive=0.10):
    return (2.0 * drive * audio) / (1 + 1.8 * drive * np.abs(audio))


def gen_pink(n, sr=24000, level=0.002):
    white = np.random.randn(n).astype(np.float32)
    from scipy.signal import butter, lfilter
    b, a = butter(2, 700 / (0.5 * sr), btype='low')
    pink = lfilter(b, a, white)
    mx = np.max(np.abs(pink))
    if mx > 0:
        pink = pink / mx * level
    return pink


def gen_crackle(n, sr=24000, rate=0.00008, level=0.004):
    c = np.zeros(n, dtype=np.float32)
    num = int(n * rate)
    for _ in range(num):
        pos = np.random.randint(0, n)
        length = np.random.randint(2, 12)
        end = min(pos + length, n)
        env = np.exp(-np.linspace(0, 4, end - pos))
        c[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return c


def gen_hum(n, sr=24000, level=0.001):
    t = np.linspace(0, n / sr, n, dtype=np.float32)
    return (np.sin(2 * np.pi * 50 * t) * level +
            np.sin(2 * np.pi * 100 * t) * level * 0.3)


def apply_vintage(audio, sr):
    audio = bandpass_filter(audio, sr, 350, 3500)
    audio = add_distortion(audio, 0.10)
    audio = audio + gen_pink(len(audio), sr, 0.002) + gen_crackle(len(audio), sr) + gen_hum(len(audio), sr)
    fade = int(sr * 0.04)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    mx = np.max(np.abs(audio))
    if mx > 0:
        audio = audio / mx * 0.9
    return audio


def load_mp3(path):
    from scipy.io import wavfile
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        tmp = path.replace('.mp3', '_t.wav')
        subprocess.run([ffmpeg, '-y', '-i', path, '-ar', '24000', '-ac', '1', tmp], capture_output=True)
        if os.path.exists(tmp):
            sr, a = wavfile.read(tmp)
            os.remove(tmp)
            return sr, a.astype(np.float32) / 32768.0
    except Exception as e:
        print(f"   ffmpeg fail: {e}")
    return None, None


def save_wav(audio, sr, path):
    from scipy.io import wavfile
    wavfile.write(path, sr, (audio * 32767).astype(np.int16))


async def tts(text, out_path):
    try:
        import edge_tts
        rate = f"+{int((SPEED - 1) * 100)}%" if SPEED > 1 else f"{int((SPEED - 1) * 100)}%"
        c = edge_tts.Communicate(text, VOICE, rate=rate)
        await c.save(out_path)
        return True
    except Exception as e:
        print(f"   TTS fail: {e}")
        return False


async def gen_one(item):
    pid = item["id"]
    text = item["text"]
    year = item["year"]
    month = item["month"]
    out_file = f"{pid}.wav"
    out_path = os.path.join(OUTPUT_DIR, out_file)
    pub_path = os.path.join(PUBLIC_DIR, out_file)

    if os.path.exists(pub_path) and os.path.getsize(pub_path) > 5000:
        print(f"   ⏭️ {pid} 已存在，跳过")
        return True
    if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
        shutil.copy2(out_path, pub_path)
        print(f"   ⏭️ {pid} 已生成，复制到public")
        return True

    print(f"🎙️ {pid} ({year}年{month}月): {text[:30]}...")

    tmp_dir = tempfile.gettempdir()
    tmp_mp3 = os.path.join(tmp_dir, f"life_tts_{pid}.mp3")

    ok = await tts(text, tmp_mp3)
    if not ok:
        print(f"   ❌ TTS失败")
        return False

    sr, audio = load_mp3(tmp_mp3)
    if sr is None:
        return False
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage(audio, sr)
    save_wav(audio, sr, out_path)
    shutil.copy2(out_path, pub_path)
    print(f"   ✅ {out_file} ({len(audio)/sr:.1f}秒)")

    try:
        if os.path.exists(tmp_mp3):
            os.remove(tmp_mp3)
    except:
        pass
    return True


async def main():
    print("=" * 60)
    print("时光调频 · 月度生活片段TTS批量生成器 (1949-1960)")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    life_list = data["life_snippets"]
    print(f"\n📋 待生成: {len(life_list)} 条月度生活片段")
    print(f"📂 输出: {OUTPUT_DIR}")
    print(f"📂 同步: {PUBLIC_DIR}")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    success = 0
    fail = 0
    batch_size = 3

    for i in range(0, len(life_list), batch_size):
        batch = life_list[i:i+batch_size]
        tasks = [gen_one(item) for item in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                success += 1
            else:
                fail += 1

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(life_list)}, 失败: {fail}")


if __name__ == "__main__":
    asyncio.run(main())
