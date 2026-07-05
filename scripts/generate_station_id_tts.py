#!/usr/bin/env python3
"""
生成台呼(Station ID)和过渡(Jingle)TTS音频。
台呼：开场白/节目预告类（如"中央人民广播电台"）
过渡：节目间短过渡（如"请继续收听"）
使用 edge-tts 生成语音，添加50年代老式广播效果。
"""
import asyncio
import os
import sys
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "station-id-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.85

STATION_IDS = [
    {"id": "id_001", "year": 1950, "text": "中央人民广播电台。", "effect": "clean"},
    {"id": "id_002", "year": 1955, "text": "中央人民广播电台，现在是新闻节目时间。", "effect": "clean"},
    {"id": "id_003", "year": 1958, "text": "中央人民广播电台，各位听众同志们好。", "effect": "clean"},
    {"id": "id_004", "year": 1960, "text": "中央人民广播电台，现在继续播音。", "effect": "clean"},
    {"id": "id_005", "year": 1960, "text": "这里是中央人民广播电台。", "effect": "clean"},
    {"id": "id_006", "year": 1960, "text": "中央台。请继续收听本台广播。", "effect": "clean"},
    {"id": "id_007", "year": 1950, "text": "中央人民广播电台，现在开始广播。", "effect": "clean"},
    {"id": "id_008", "year": 1960, "text": "中央人民广播电台，同志们，朋友们，你们好。", "effect": "clean"},
]

JINGLES = [
    {"id": "jingle_001", "year": 1950, "text": "请继续收听。", "effect": "light"},
    {"id": "jingle_002", "year": 1960, "text": "下面请继续收听。", "effect": "light"},
    {"id": "jingle_003", "year": 1960, "text": "接下来请您继续收听。", "effect": "light"},
    {"id": "jingle_004", "year": 1955, "text": "请您继续收听本台节目。", "effect": "light"},
]


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


def gen_pink(n, sr=24000, level=0.003):
    white = np.random.randn(n).astype(np.float32)
    from scipy.signal import butter, lfilter
    b, a = butter(2, 700 / (0.5 * sr), btype='low')
    pink = lfilter(b, a, white)
    mx = np.max(np.abs(pink))
    if mx > 0:
        pink = pink / mx * level
    return pink


def gen_crackle(n, sr=24000, rate=0.0001, level=0.005):
    c = np.zeros(n, dtype=np.float32)
    num = int(n * rate)
    for _ in range(num):
        pos = np.random.randint(0, n)
        length = np.random.randint(2, 10)
        end = min(pos + length, n)
        env = np.exp(-np.linspace(0, 4, end - pos))
        c[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return c


def gen_hum(n, sr=24000, level=0.001):
    t = np.linspace(0, n / sr, n, dtype=np.float32)
    return (np.sin(2 * np.pi * 50 * t) * level +
            np.sin(2 * np.pi * 100 * t) * level * 0.3)


def apply_vintage(audio, sr, effect="clean"):
    if effect == "light":
        audio = bandpass_filter(audio, sr, 400, 3800)
        audio = add_distortion(audio, 0.08)
        audio = audio + gen_pink(len(audio), sr, 0.002) + gen_hum(len(audio), sr, 0.0008)
        fade = int(sr * 0.03)
        target = 0.88
    else:
        audio = bandpass_filter(audio, sr, 350, 3500)
        audio = add_distortion(audio, 0.10)
        audio = audio + gen_pink(len(audio), sr, 0.003) + gen_crackle(len(audio), sr) + gen_hum(len(audio), sr)
        fade = int(sr * 0.05)
        target = 0.9
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    mx = np.max(np.abs(audio))
    if mx > 0:
        audio = audio / mx * target
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
    base_name = item["id"]
    out_wav = os.path.join(OUTPUT_DIR, f"{base_name}.wav")
    out_m4a = os.path.join(OUTPUT_DIR, f"{base_name}.m4a")
    pub_m4a = os.path.join(PUBLIC_DIR, f"{base_name}.m4a")

    if os.path.exists(pub_m4a) and os.path.getsize(pub_m4a) > 2000:
        return True

    text = item["text"]
    effect = item.get("effect", "clean")
    tmp_dir = tempfile.gettempdir()
    tmp_mp3 = os.path.join(tmp_dir, f"sid_tts_{base_name}.mp3")

    ok = await tts(text, tmp_mp3)
    if not ok:
        return False

    sr, audio = load_mp3(tmp_mp3)
    if sr is None:
        return False
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage(audio, sr, effect)
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
    print(f"  ✅ {base_name}.m4a ({duration:.1f}s) [{item['year']}]: {text}")
    return True


async def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    print("=" * 60)
    print("时光调频 · 台呼/过渡音频TTS生成器")
    print(f"语速: {SPEED}x  声音: {VOICE}")
    print(f"台呼: {len(STATION_IDS)} 个, 过渡: {len(JINGLES)} 个")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    all_items = STATION_IDS + JINGLES
    print(f"\n📊 待生成: {len(all_items)} 个音频")
    print()

    success = 0
    fail = 0

    coros = [gen_one(item) for item in all_items]
    results = await asyncio.gather(*coros, return_exceptions=True)
    for item, r in zip(all_items, results):
        if r is True:
            success += 1
        else:
            fail += 1
            if isinstance(r, Exception):
                print(f"  ❌ {item['id']}: {r}")
            else:
                print(f"  ❌ {item['id']}")

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(all_items)}, 失败: {fail}")


if __name__ == "__main__":
    asyncio.run(main())
