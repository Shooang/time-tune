#!/usr/bin/env python3
"""
生成日期天气开场TTS音频（1949-1960）：
- 简短版(date_short_YYYY_MM.wav): "中央人民广播电台。"（144个，每月1个）
- 完整版(date_YYYY_MM_DD.wav): 含日期+星期+农历+天气（按年代分支）
  * 1949-1954：台呼+问候+日期+农历（无节目名、无天气）
  * 1955-1956.5：台呼+节目名+问候+日期+农历（有节目名、无天气）
  * 1956.6-1960：台呼+节目名+问候+日期+农历+天气（完整版）
使用 zh-CN-YunyangNeural, speed=0.88，带vintage_50s轻量后处理。
"""
import asyncio
import os
import sys
import random
import tempfile
import shutil
import datetime
import calendar
import numpy as np

try:
    from zhdate import ZhDate
except ImportError:
    os.system(f"{sys.executable} -m pip install zhdate -q")
    from zhdate import ZhDate

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "date-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.88

YEAR_CN = {
    1949: "一九四九", 1950: "一九五零", 1951: "一九五一", 1952: "一九五二",
    1953: "一九五三", 1954: "一九五四", 1955: "一九五五", 1956: "一九五六",
    1957: "一九五七", 1958: "一九五八", 1959: "一九五九", 1960: "一九六零",
}

MONTH_CN_READ = [
    "", "一月", "二月", "三月", "四月", "五月", "六月",
    "七月", "八月", "九月", "十月", "十一月", "十二月"
]

NUM_CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def day_to_cn_lunar(day: int) -> str:
    if day == 10:
        return "初十"
    if day == 20:
        return "二十"
    if day == 30:
        return "三十"
    if day < 10:
        return f"初{NUM_CN[day]}"
    if day < 20:
        return f"十{NUM_CN[day - 10]}"
    return f"二十{NUM_CN[day - 20]}"


def day_to_cn_solar(day: int) -> str:
    if day == 10:
        return "十日"
    if day == 20:
        return "二十日"
    if day == 30:
        return "三十日"
    if day < 10:
        return f"{NUM_CN[day]}日"
    if day < 20:
        return f"十{NUM_CN[day - 10]}日"
    if day < 30:
        return f"二十{NUM_CN[day - 20]}日"
    if day == 31:
        return "三十一日"
    return f"{day}日"


def lunar_to_cn(zh: ZhDate) -> str:
    m = zh.lunar_month
    d = zh.lunar_day
    leap = zh.leap_month
    prefix = "闰" if leap else ""
    m_str = MONTH_CN_READ[m] if m <= 12 else ""
    d_str = day_to_cn_lunar(d)
    return f"{prefix}{m_str}{d_str}"


def get_days_in_month(y: int, m: int) -> int:
    return calendar.monthrange(y, m)[1]


WEATHER_PROFILES = {
    1: [("晴", -5, 5), ("多云", -7, 3), ("阴有小雪", -10, -2)],
    2: [("晴", -3, 8), ("多云", -5, 5), ("阴转晴", -2, 6)],
    3: [("晴间多云", 5, 15), ("晴", 8, 18), ("多云", 3, 12)],
    4: [("晴", 12, 22), ("多云", 10, 20), ("晴转多云", 14, 24)],
    5: [("晴", 18, 28), ("晴间多云", 16, 26), ("多云转阴", 15, 24)],
    6: [("晴", 24, 34), ("晴午后有雷阵雨", 23, 33), ("多云", 22, 31)],
    7: [("晴间多云", 26, 35), ("午后雷阵雨", 25, 33), ("晴热", 28, 36)],
    8: [("晴", 25, 34), ("多云有阵雨", 23, 31), ("晴间多云", 24, 33)],
    9: [("晴", 18, 28), ("多云转晴", 16, 25), ("晴间多云", 17, 26)],
    10: [("晴", 10, 20), ("多云", 8, 18), ("晴转多云", 9, 19)],
    11: [("晴", 2, 12), ("多云", 0, 10), ("阴转晴", -1, 8)],
    12: [("晴", -6, 4), ("多云", -8, 2), ("晴间多云", -5, 5)],
}

WEATHER_CUTOFF = datetime.datetime(1956, 6, 1)
PROGRAM_NAME_CUTOFF = 1955


def get_weather(y: int, m: int, d: int) -> tuple:
    profiles = WEATHER_PROFILES[m]
    rng = random.Random(f"{y}-{m}-{d}")
    desc, low_base, high_base = rng.choice(profiles)
    low = low_base + rng.randint(-2, 2)
    high = high_base + rng.randint(-2, 2)
    return desc, high, low


SHORT_VARIANTS = [
    "中央人民广播电台。",
    "中央台。",
    "现在开始广播。",
    "这里是中央人民广播电台。",
    "中央人民广播电台，现在开始播音。",
]

TIME_PERIODS = {
    "dawn": {
        "hours": (0, 5),
        "variants": [
            "各位听众，夜间好。",
            "同志们，深夜好。",
            "夜间还在收听广播的朋友们，你们好。",
            "各位听众同志们，深夜好。",
        ]
    },
    "morning": {
        "hours": (5, 8),
        "variants": [
            "各位听众同志们，早上好！",
            "同志们，早晨好！",
            "听众朋友们，大家早！",
            "各位早上好！",
        ]
    },
    "forenoon": {
        "hours": (8, 11),
        "variants": [
            "各位听众，上午好！",
            "同志们，上午好！",
            "各位听众同志们，上午好。",
            "听众朋友们，上午好。",
        ]
    },
    "noon": {
        "hours": (11, 13),
        "variants": [
            "各位听众同志们，中午好！",
            "同志们，午间好！",
            "各位听众，中午好。",
            "听众朋友们，中午好。",
        ]
    },
    "afternoon": {
        "hours": (13, 17),
        "variants": [
            "各位听众，下午好！",
            "同志们，下午好！",
            "各位听众同志们，下午好。",
            "欢迎继续收听本台广播，各位下午好。",
        ]
    },
    "evening": {
        "hours": (17, 21),
        "variants": [
            "各位听众同志们，晚上好！",
            "同志们，晚上好！",
            "听众朋友们，晚上好。",
            "各位晚上好！",
        ]
    },
    "night": {
        "hours": (21, 24),
        "variants": [
            "各位听众，晚上好！",
            "同志们，夜间好。",
            "各位听众同志们，晚上好。",
            "夜间还在收听的同志们，你们好。",
        ]
    },
}


def get_time_period(hour: int) -> str:
    for period_id, period in TIME_PERIODS.items():
        h_start, h_end = period["hours"]
        if h_start <= hour < h_end:
            return period_id
    return "night"


def build_short_text(year: int, month: int) -> str:
    rng = random.Random(f"{year}_{month}")
    return rng.choice(SHORT_VARIANTS)


PROGRAM_NAME_TEXT = "现在是《新闻和报纸摘要》节目时间。"


def build_full_text(y: int, m: int, d: int) -> str:
    dt = datetime.datetime(y, m, d)
    wd = WEEKDAY_CN[dt.weekday()]
    zh = ZhDate.from_datetime(dt)
    lunar_str = lunar_to_cn(zh)
    year_cn = YEAR_CN[y]
    month_cn = MONTH_CN_READ[m]
    day_cn = day_to_cn_solar(d)

    has_program_name = y >= PROGRAM_NAME_CUTOFF
    has_weather = dt >= WEATHER_CUTOFF

    rng = random.Random(f"{y}_{m}_intro")
    variant_idx = rng.randint(0, 5)

    date_part = f"今天是{year_cn}年{month_cn}{day_cn}，{wd}，农历{lunar_str}。"

    if variant_idx == 0:
        if has_program_name:
            intro = f"中央人民广播电台，{PROGRAM_NAME_TEXT}"
        else:
            intro = "中央人民广播电台。"
    elif variant_idx == 1:
        intro = "欢迎收听中央人民广播电台的广播。"
        if has_program_name:
            intro = f"{PROGRAM_NAME_TEXT}"
    elif variant_idx == 2:
        intro = "中央人民广播电台，中央人民广播电台。"
        if has_program_name:
            intro = f"中央人民广播电台，中央人民广播电台。{PROGRAM_NAME_TEXT}"
    elif variant_idx == 3:
        intro = "同志们，朋友们，这里是中央台。"
        if has_program_name:
            intro = f"同志们，朋友们，这里是中央台。{PROGRAM_NAME_TEXT}"
    elif variant_idx == 4:
        intro = "收音机前的各位听众。"
        if has_program_name:
            intro += PROGRAM_NAME_TEXT
    elif variant_idx == 5:
        if has_program_name:
            intro = f"中央台。{PROGRAM_NAME_TEXT}"
        else:
            intro = "中央台。"
    else:
        intro = "中央人民广播电台。"

    base = intro + date_part

    if has_weather:
        desc, high, low = get_weather(y, m, d)
        base += f"北京天气{desc}，最高气温{high}度，最低气温{low}度。"
    return base


DATE_FULL_DAYS = {
    "1949_01": [12,23,30], "1949_02": [1,3,20], "1949_03": [9,24,28], "1949_04": [14,25,27],
    "1949_05": [1,5,12], "1949_06": [6,9,15], "1949_07": [8,28,31], "1949_08": [5,25,28],
    "1949_09": [7,22,26], "1949_10": [2,14,22], "1949_11": [12,20,23], "1949_12": [24,26,30],
    "1950_01": [6,7,31], "1950_02": [5,6,11], "1950_03": [10,18,19], "1950_04": [3,7,23],
    "1950_05": [19,28,31], "1950_06": [9,21,25], "1950_07": [17,25,31], "1950_08": [9,20,22],
    "1950_09": [2,11,12], "1950_10": [8,19,25], "1950_11": [2,19,23], "1950_12": [8,12,24],
    "1951_01": [14,20,27], "1951_02": [7,12,15], "1951_03": [4,15,27], "1951_04": [14,19,22],
    "1951_05": [5,13,27], "1951_06": [9,23,26], "1951_07": [9,19,20], "1951_08": [3,17,20],
    "1951_09": [12,15,24], "1951_10": [6,7,9], "1951_11": [2,16,18], "1951_12": [2,14,26],
    "1952_01": [1,24,29], "1952_02": [7,20,25], "1952_03": [1,7,20], "1952_04": [7,25,26],
    "1952_05": [13,25,30], "1952_06": [5,16,24], "1952_07": [15,20,28], "1952_08": [5,7,12],
    "1952_09": [4,15,27], "1952_10": [6,26,27], "1952_11": [13,14,22], "1952_12": [4,17,27],
    "1953_01": [4,21,24], "1953_02": [3,13,26], "1953_03": [3,4,28], "1953_04": [7,21,25],
    "1953_05": [10,13,20], "1953_06": [1,17,25], "1953_07": [2,17,29], "1953_08": [3,23,26],
    "1953_09": [8,24,25], "1953_10": [4,16,18], "1953_11": [8,24,29], "1953_12": [13,20,30],
    "1954_01": [7,23,28], "1954_02": [11,16,17], "1954_03": [8,12,31], "1954_04": [22,23,30],
    "1954_05": [6,11,25], "1954_06": [5,15,26], "1954_07": [1,4,12], "1954_08": [1,15,16],
    "1954_09": [11,21,26], "1954_10": [2,11,31], "1954_11": [7,26,28], "1954_12": [6,18,22],
    "1955_01": [10,11,30], "1955_02": [7,12,25], "1955_03": [12,13,17], "1955_04": [9,13,29],
    "1955_05": [2,4,18], "1955_06": [2,9,15], "1955_07": [7,18,22], "1955_08": [5,30,31],
    "1955_09": [8,19,23], "1955_10": [13,14,25], "1955_11": [1,12,29], "1955_12": [3,25,27],
    "1956_01": [3,14,22], "1956_02": [10,11,26], "1956_03": [5,17,21], "1956_04": [12,17,25],
    "1956_05": [14,15,31], "1956_06": [13,20,29], "1956_07": [3,7,31], "1956_08": [11,16,23],
    "1956_09": [5,9,10], "1956_10": [2,5,30], "1956_11": [18,27,28], "1956_12": [5,8,21],
    "1957_01": [3,7,27], "1957_02": [3,9,25], "1957_03": [12,17,20], "1957_04": [2,6,25],
    "1957_05": [6,12,23], "1957_06": [16,23,27], "1957_07": [9,28,30], "1957_08": [1,2,15],
    "1957_09": [14,20,24], "1957_10": [6,21,28], "1957_11": [6,14,27], "1957_12": [4,8,21],
    "1958_01": [10,19,22], "1958_02": [11,24,25], "1958_03": [2,3,15], "1958_04": [4,12,27],
    "1958_05": [3,15,19], "1958_06": [10,11,19], "1958_07": [7,18,31], "1958_08": [1,14,28],
    "1958_09": [4,8,25], "1958_10": [3,11,14], "1958_11": [9,23,26], "1958_12": [8,11,14],
    "1959_01": [12,17,21], "1959_02": [4,7,18], "1959_03": [21,23,26], "1959_04": [4,8,27],
    "1959_05": [18,21,28], "1959_06": [2,11,24], "1959_07": [20,26,28], "1959_08": [5,21,29],
    "1959_09": [21,23,27], "1959_10": [8,15,28], "1959_11": [8,13,27], "1959_12": [7,27,31],
    "1960_01": [3,25,28], "1960_02": [4,6,20], "1960_03": [1,3,13], "1960_04": [4,13,24],
    "1960_05": [7,8,25], "1960_06": [2,6,20], "1960_07": [13,27,28], "1960_08": [13,19,30],
    "1960_09": [6,7,26], "1960_10": [3,4,8], "1960_11": [15,21,26], "1960_12": [4,17,29],
}


def get_days_for_month(y: int, m: int) -> list:
    key = f"{y}_{m:02d}"
    return DATE_FULL_DAYS.get(key, [1, 15, 28])


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


async def gen_one(text, out_file):
    out_m4a = out_file.replace('.wav', '.m4a')
    out_path = os.path.join(OUTPUT_DIR, out_file)
    out_path_m4a = os.path.join(OUTPUT_DIR, out_m4a)
    pub_path = os.path.join(PUBLIC_DIR, out_m4a)
    if os.path.exists(pub_path) and os.path.getsize(pub_path) > 3000:
        return True
    if os.path.exists(out_path_m4a) and os.path.getsize(out_path_m4a) > 3000:
        shutil.copy2(out_path_m4a, pub_path)
        return True
    tmp_dir = tempfile.gettempdir()
    tmp_mp3 = os.path.join(tmp_dir, f"tts_{out_file.replace('.wav','.mp3')}")
    ok = await tts(text, tmp_mp3)
    if not ok:
        return False
    sr, audio = load_mp3(tmp_mp3)
    if sr is None:
        return False
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)
    audio = apply_vintage(audio, sr)
    save_wav(audio, sr, out_path)
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        cmd = [ffmpeg_exe, '-y', '-i', out_path, '-c:a', 'aac', '-b:a', '128k', '-ar', '24000', '-ac', '1', out_path_m4a]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_path_m4a):
            shutil.copy2(out_path_m4a, pub_path)
        else:
            shutil.copy2(out_path, pub_path.replace('.m4a', '.wav'))
    except Exception as e:
        print(f"   m4a convert fail: {e}, fallback wav")
        shutil.copy2(out_path, pub_path.replace('.m4a', '.wav'))
    try:
        os.remove(tmp_mp3)
    except:
        pass
    return True


async def main():
    print("=" * 60)
    print("时光调频 · 日期开场TTS生成器 v3（时段问候分离）")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    tasks = []

    for period_id, period in TIME_PERIODS.items():
        for i, text in enumerate(period["variants"], 1):
            greet_file = f"greet_{period_id}_{i:02d}.wav"
            tasks.append(("greet", text, greet_file))

    for y in range(1949, 1961):
        for m in range(1, 13):
            short_file = f"date_short_{y}_{m:02d}.wav"
            short_text = build_short_text(y, m)
            tasks.append(("short", short_text, short_file))

            days = get_days_for_month(y, m)
            for d in days:
                full_file = f"date_{y}_{m:02d}_{d:02d}.wav"
                full_text = build_full_text(y, m, d)
                tasks.append(("full", full_text, full_file))

    print(f"\n📊 待生成: {len(tasks)} 个音频 ({sum(1 for t in tasks if t[0]=='greet')} 时段问候 + {sum(1 for t in tasks if t[0]=='short')} 简短 + {sum(1 for t in tasks if t[0]=='full')} 完整)")
    print()

    success = 0
    fail = 0
    batch = 5

    for i in range(0, len(tasks), batch):
        bt = tasks[i:i + batch]
        coros = [gen_one(text, fn) for _, text, fn in bt]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for (kind, text, fn), r in zip(bt, results):
            if r is True:
                success += 1
                label = "短" if kind == "short" else "全"
                if kind == "full":
                    print(f"  ✅ [{label}] {fn}: {text[:60]}...")
                else:
                    print(f"  ✅ [{label}] {fn}")
            else:
                fail += 1
                print(f"  ❌ {fn}")

    print(f"\n{'=' * 60}")
    print(f"✨ TTS完成：成功 {success}/{len(tasks)}, 失败 {fail}")


def test_variants():
    print("=" * 60)
    print("测试开场多样性")
    print("=" * 60)
    print()

    shorts = set()
    for y in range(1949, 1961):
        for m in range(1, 13):
            shorts.add(build_short_text(y, m))
    print(f"Short 变体数量: {len(shorts)}")
    for i, s in enumerate(sorted(shorts), 1):
        print(f"  {i}. {s}")
    print()

    full_intros = set()
    for y in range(1949, 1961):
        for m in range(1, 13):
            d = 1
            dt = datetime.datetime(y, m, d)
            zh = ZhDate.from_datetime(dt)
            wd = WEEKDAY_CN[dt.weekday()]
            lunar_str = lunar_to_cn(zh)
            year_cn = YEAR_CN[y]
            month_cn = MONTH_CN_READ[m]
            day_cn = day_to_cn_solar(d)
            date_part = f"今天是{year_cn}年{month_cn}{day_cn}，{wd}，农历{lunar_str}。"
            text = build_full_text(y, m, d)
            intro = text.split(date_part)[0]
            full_intros.add(intro)
    print(f"Full 开场白变体数量: {len(full_intros)}")
    for i, intro in enumerate(sorted(full_intros), 1):
        print(f"  {i}. {intro}")
    print()

    test_dates = [
        (1949, 1, 15),
        (1950, 6, 15),
        (1955, 3, 15),
        (1956, 7, 15),
        (1958, 10, 15),
        (1960, 12, 15),
    ]
    print("完整文本示例:")
    for y, m, d in test_dates:
        text = build_full_text(y, m, d)
        print(f"\n{y}-{m:02d}-{d:02d}:")
        print(f"  {text}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_variants()
    else:
        asyncio.run(main())
