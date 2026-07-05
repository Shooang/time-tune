#!/usr/bin/env python3
"""
批量生成天气预报TTS音频（1949年1月-1960年12月）。
使用 edge-tts 生成语音，添加50年代老式广播效果。
- 1949-1955：中央气象台成立前，以"本台消息""农事建议"形式播报
- 1956-1960：正式天气预报，温度精确
"""
import asyncio
import os
import sys
import random
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "weather-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.88

WEATHER_PROFILES = {
    1: [("晴", -5, 5), ("多云", -7, 3), ("阴有小雪", -10, -2), ("晴间多云", -4, 4)],
    2: [("晴", -3, 8), ("多云", -5, 5), ("阴转晴", -2, 6), ("晴间多云", -1, 7)],
    3: [("晴间多云", 5, 15), ("晴", 8, 18), ("多云", 3, 12), ("晴转多云", 6, 16)],
    4: [("晴", 12, 22), ("多云", 10, 20), ("晴转多云", 14, 24), ("多云转阴", 11, 19)],
    5: [("晴", 18, 28), ("晴间多云", 16, 26), ("多云转阴", 15, 24), ("晴午后有阵雨", 17, 27)],
    6: [("晴", 24, 34), ("晴午后有雷阵雨", 23, 33), ("多云", 22, 31), ("晴间多云", 25, 33)],
    7: [("晴间多云", 26, 35), ("午后雷阵雨", 25, 33), ("晴热", 28, 36), ("多云有阵雨", 24, 32)],
    8: [("晴", 25, 34), ("多云有阵雨", 23, 31), ("晴间多云", 24, 33), ("晴热", 27, 35)],
    9: [("晴", 18, 28), ("多云转晴", 16, 25), ("晴间多云", 17, 26), ("多云", 15, 24)],
    10: [("晴", 10, 20), ("多云", 8, 18), ("晴转多云", 9, 19), ("晴间多云", 11, 21)],
    11: [("晴", 2, 12), ("多云", 0, 10), ("阴转晴", -1, 8), ("晴间多云", 3, 13)],
    12: [("晴", -6, 4), ("多云", -8, 2), ("晴间多云", -5, 5), ("阴有小雪", -10, -1)],
}

PREFIX_VARIANTS = [
    "下面播报天气预报。",
    "现在为您播报天气情况。",
    "接下来是天气预报节目。",
    "各位听众，下面播报北京地区天气预报。",
    "天气预报时间。",
    "现在播送天气预报。",
]

EARLY_PREFIX_VARIANTS = [
    "本台消息，根据听众来信和各地反映，",
    "各位听众同志们，根据各地通讯员报告，",
    "现在报告一下天气情况，供大家安排生产生活参考。",
    "这里报告一下最近的天气趋势，",
    "根据农事需要，报告一下近日天气，",
    "各位老乡，眼下的天气情况是这样的，",
]

SUFFIX_VARIANTS = [
    "以上是天气预报。",
    "天气预报播送完了。",
    "",
    "",
]

EARLY_SUFFIX_VARIANTS = [
    "请各位乡亲根据天气情况安排好生产。",
    "以上天气情况供同志们参考。",
    "请大家注意天气变化。",
    "",
    "",
]


def get_weather(y, m, variant_idx):
    profiles = WEATHER_PROFILES[m]
    rng = random.Random(f"weather_{y}_{m}_{variant_idx}")
    desc, low_base, high_base = rng.choice(profiles)
    low = low_base + rng.randint(-2, 2)
    high = high_base + rng.randint(-2, 2)
    return desc, high, low


def build_weather_text(y, m, variant_idx):
    rng = random.Random(f"wtext_{y}_{m}_{variant_idx}")
    desc, high, low = get_weather(y, m, variant_idx)
    is_early = y < 1956

    if is_early:
        prefix = rng.choice(EARLY_PREFIX_VARIANTS)
        suffix = rng.choice(EARLY_SUFFIX_VARIANTS)
        temp_desc = f"天气{desc}，气温大约在{low}度到{high}度之间。"
        if high >= 32:
            advice = "天气炎热，下地干活要注意防暑，多喝凉白开。"
        elif low <= -5:
            advice = "天气寒冷，同志们要注意添衣保暖，小心冻害。"
        elif "雪" in desc:
            advice = "雪天路滑，出门要注意安全。"
        elif "雷阵雨" in desc or "阵雨" in desc:
            advice = "有雨的天气，出门别忘带雨具，地里庄稼也要注意排涝。"
        elif m in (3, 4):
            advice = "眼下正是春耕时节，同志们要抓紧农时。"
        elif m in (9, 10):
            advice = "秋收秋种的时节，请乡亲们注意抢收抢种。"
        else:
            advice = ""
        body = temp_desc + advice
    else:
        prefix = rng.choice(PREFIX_VARIANTS)
        suffix = rng.choice(SUFFIX_VARIANTS)
        body = f"北京地区，今天{desc}，最高气温{high}度，最低气温{low}度。"
        if high >= 32:
            body += "天气炎热，请同志们注意防暑降温。"
        elif low <= -5:
            body += "天气寒冷，请注意添衣保暖。"
        elif "雪" in desc:
            body += "请同志们注意出行安全。"
        elif "雷阵雨" in desc or "阵雨" in desc:
            body += "出门请带好雨具。"

    text = prefix + body + suffix
    return text


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
    fade = int(sr * 0.05)
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


async def gen_one(y, m, variant_idx):
    base_name = f"weather_{y}_{m:02d}_{variant_idx}"
    out_wav = os.path.join(OUTPUT_DIR, f"{base_name}.wav")
    out_m4a = os.path.join(OUTPUT_DIR, f"{base_name}.m4a")
    pub_m4a = os.path.join(PUBLIC_DIR, f"{base_name}.m4a")

    if os.path.exists(pub_m4a) and os.path.getsize(pub_m4a) > 3000:
        return True

    text = build_weather_text(y, m, variant_idx)
    tmp_dir = tempfile.gettempdir()
    tmp_mp3 = os.path.join(tmp_dir, f"weather_tts_{base_name}.mp3")

    ok = await tts(text, tmp_mp3)
    if not ok:
        return False

    sr, audio = load_mp3(tmp_mp3)
    if sr is None:
        return False
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage(audio, sr)
    save_wav(audio, sr, out_wav)

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        cmd = [ffmpeg_exe, '-y', '-i', out_wav, '-c:a', 'aac', '-b:a', '128k', '-ar', '24000', '-ac', '1', out_m4a]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_m4a):
            shutil.copy2(out_m4a, pub_m4a)
        else:
            shutil.copy2(out_wav, pub_m4a.replace('.m4a', '.wav'))
    except Exception as e:
        print(f"   m4a convert fail: {e}, fallback wav")
        shutil.copy2(out_wav, pub_m4a.replace('.m4a', '.wav'))

    try:
        os.remove(tmp_mp3)
    except:
        pass

    duration = len(audio) / sr
    print(f"  ✅ {base_name}.m4a ({duration:.1f}s): {text[:50]}...")
    return True


async def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    print("=" * 60)
    print("时光调频 · 天气预报TTS生成器")
    print(f"语速: {SPEED}x  声音: {VOICE}")
    print("覆盖: 1949年1月 ~ 1960年12月，每月3条变体")
    print("  - 1949-1955: 建国初期语气（本台消息/农事建议）")
    print("  - 1956-1960: 正式天气预报（精确温度）")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    tasks = []
    for y in range(1949, 1961):
        for m in range(1, 13):
            for v in range(1, 4):
                tasks.append((y, m, v))

    print(f"\n📊 待生成: {len(tasks)} 个天气播报音频")
    print()

    success = 0
    fail = 0
    batch = 5

    for i in range(0, len(tasks), batch):
        bt = tasks[i:i + batch]
        coros = [gen_one(y, m, v) for y, m, v in bt]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for (y, m, v), r in zip(bt, results):
            if r is True:
                success += 1
            else:
                fail += 1
                if isinstance(r, Exception):
                    print(f"  ❌ weather_{y}_{m:02d}_{v}: {r}")
                else:
                    print(f"  ❌ weather_{y}_{m:02d}_{v}")

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(tasks)}, 失败: {fail}")


if __name__ == "__main__":
    asyncio.run(main())
