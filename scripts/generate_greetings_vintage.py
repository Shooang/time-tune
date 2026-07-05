#!/usr/bin/env python3
"""
批量生成年代分组时段问候语TTS音频。
3个年代分组 × 7个时段 × 4个变体 = 84条问候语。
- early: 1949-1952（建国初期）语气庄重，"各位听众同志们"
- mid:   1953-1957（一五计划）建设话语，"亲爱的听众"
- late:  1958-1960（大跃进）语气激昂，"鼓足干劲"
"""
import asyncio
import os
import sys
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "greetings-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.88

GREETINGS = {
    "early": {
        "dawn": [
            "各位听众同志们，凌晨好。天还没亮，新的一天即将开始。",
            "同志们，凌晨好。远方已经露出微微的鱼肚白。",
            "各位听众，凌晨好。让我们迎接新中国的又一个黎明。",
            "听众同志们，凌晨好。早起的同志们，辛苦了。",
        ],
        "morning": [
            "各位听众同志们，早上好！太阳升起来了，新的一天开始了。",
            "同志们，早晨好！让我们满怀热情投入到新的工作中去。",
            "各位听众，早上好。朝霞映照着祖国大地，人们开始了一天的劳动。",
            "听众同志们，清晨好。一日之计在于晨，让我们抓紧时间，努力工作。",
        ],
        "forenoon": [
            "各位听众同志们，上午好。工作进行得怎么样了？",
            "同志们，上午好。各条战线的同志们正在辛勤劳动。",
            "各位听众，上午好。希望大家鼓足干劲，把上午的工作做好。",
            "听众同志们，上午好。让我们抓紧时间，完成今天的生产任务。",
        ],
        "noon": [
            "各位听众同志们，中午好。到了歇晌的时间了。",
            "同志们，午安。忙碌了一上午，该歇歇了，吃了饭再接着干。",
            "各位听众，中午好。吃过午饭，稍事休息，下午继续奋斗。",
            "听众同志们，中午好。工地上、车间里、田埂上，同志们先吃口饭。",
        ],
        "afternoon": [
            "各位听众同志们，下午好。继续我们的工作和劳动。",
            "同志们，下午好。坚持就是胜利，把今天的任务完成好。",
            "各位听众，下午好。太阳偏西了，但我们的干劲不能减。",
            "听众同志们，下午好。工厂的机器在轰鸣，田里的庄稼在生长。",
        ],
        "evening": [
            "各位听众同志们，傍晚好。辛苦了一天，该收工了。",
            "同志们，晚上好。吃过晚饭，听听广播，休息休息。",
            "各位听众，傍晚好。炊烟升起，各家各户开始准备晚饭了。",
            "听众同志们，晚上好。劳动了一天，好好歇歇，明天继续干。",
        ],
        "night": [
            "各位听众同志们，夜深了。还没睡的同志们，早些休息吧。",
            "同志们，晚安。夜深了，注意关好门窗，注意防火防盗。",
            "各位听众，夜已经深了。值夜班的同志们，你们辛苦了。",
            "听众同志们，夜深了。好好睡一觉，明天还有更重要的任务等着我们。",
        ],
    },
    "mid": {
        "dawn": [
            "亲爱的听众同志们，凌晨好。祖国大地上，新的一天即将来临。",
            "各位听众，凌晨好。启明星已经挂在天边了。",
            "听众朋友们，凌晨好。早起的人们已经开始忙碌了。",
            "同志们，凌晨好。让我们迎接第一个五年计划的又一个清晨。",
        ],
        "morning": [
            "亲爱的听众同志们，早上好！今天又是建设祖国的好日子。",
            "各位听众，早上好。在这美好的清晨，让我们开始新一天的工作。",
            "听众朋友们，早晨好。建设社会主义的热情，像早晨的太阳一样高涨。",
            "同志们，早上好！为了祖国的工业化，让我们满怀信心地开始今天的劳动。",
        ],
        "forenoon": [
            "亲爱的听众同志们，上午好。工厂里热火朝天，田地里一片繁忙。",
            "各位听众，上午好。各条战线捷报频传，建设事业蒸蒸日上。",
            "听众朋友们，上午好。让我们在各自的岗位上，为国家建设贡献力量。",
            "同志们，上午好。社会主义建设离不开每一个人的辛勤劳动。",
        ],
        "noon": [
            "亲爱的听众同志们，中午好。到了午休时间，同志们好好歇一歇。",
            "各位听众，午安。吃过午饭，养足精神，下午接着干。",
            "听众朋友们，中午好。食堂里飘着饭菜香，同志们边吃边聊生产。",
            "同志们，中午好。劳动了一上午，好好休息一下，恢复体力。",
        ],
        "afternoon": [
            "亲爱的听众同志们，下午好。继续为祖国的建设添砖加瓦。",
            "各位听众，下午好。生产竞赛正在进行，同志们你追我赶。",
            "听众朋友们，下午好。工人师傅们干劲十足，农民兄弟们喜气洋洋。",
            "同志们，下午好。第一个五年计划的宏伟蓝图正在一步步变为现实。",
        ],
        "evening": [
            "亲爱的听众同志们，傍晚好。辛苦了一天，同志们该休息了。",
            "各位听众，晚上好。夕阳西下，炊烟袅袅，一家人围坐在一起吃晚饭。",
            "听众朋友们，傍晚好。生产队的记工分的时间到了，大家说说笑笑。",
            "同志们，晚上好。晚饭后听听广播，了解国家大事，也是一种学习。",
        ],
        "night": [
            "亲爱的听众同志们，夜深了。忙碌了一天，该上床休息了。",
            "各位听众，晚安。愿大家睡个好觉，做个好梦，明天精神饱满地继续工作。",
            "听众朋友们，夜已深。还在灯下学习的同志们，也该休息了。",
            "同志们，夜深了。值夜班的工友们、站岗的哨兵们，你们辛苦了。",
        ],
    },
    "late": {
        "dawn": [
            "听众同志们，凌晨好！总路线的光辉照耀着我们，新的一天开始了！",
            "各位听众，凌晨好。东方已经红了，大跃进的号角已经吹响！",
            "同志们，凌晨好。鼓足干劲，力争上游，多快好省地建设社会主义！",
            "听众朋友们，凌晨好。人民公社的社员们，已经开始早出工了！",
        ],
        "morning": [
            "听众同志们，早上好！让我们在大跃进的旗帜下，开始一天的战斗！",
            "各位听众，早上好！人有多大胆，地有多大产，同志们加油干哪！",
            "同志们，早晨好！钢铁元帅升帐了，全民大炼钢铁，同志们冲啊！",
            "听众朋友们，早上好！人民公社好，一大二公，干劲冲天！",
        ],
        "forenoon": [
            "听众同志们，上午好！工地上热火朝天，高产卫星接连上天！",
            "各位听众，上午好！超英赶美，就在今朝，同志们拿出百倍的干劲来！",
            "同志们，上午好！人民公社的田野上，红旗招展，人声鼎沸！",
            "听众朋友们，上午好！鼓足干劲搞生产，力争上游创奇迹！",
        ],
        "noon": [
            "听众同志们，中午好！歇晌不歇心，吃饭的时候也想着超产！",
            "各位听众，中午好。吃饱了饭，接着干，下午要放个大卫星！",
            "同志们，午安。公共食堂里饭菜香，同志们吃饱了继续战斗！",
            "听众朋友们，中午好。大食堂吃饭不要钱，共产主义是天堂！",
        ],
        "afternoon": [
            "听众同志们，下午好！干劲鼓得足足的，产量翻了又翻！",
            "各位听众，下午好！十五年超英赶美，我们用不了那么久！",
            "同志们，下午好！钢花四溅，铁水奔流，为了一千零七十万吨钢，冲！",
            "听众朋友们，下午好！人民公社力量大，什么困难都不怕！",
        ],
        "evening": [
            "听众同志们，傍晚好！收工不收劲，晚上还要挑灯夜战！",
            "各位听众，晚上好。高炉前灯火通明，同志们连夜奋战放卫星！",
            "同志们，傍晚好。一天的战斗结束了，捷报一个接一个！",
            "听众朋友们，晚上好。吃过晚饭，到生产队评工分、赛诗会去！",
        ],
        "night": [
            "听众同志们，夜深了。但我们的高炉还在燃烧，我们的干劲从不消减！",
            "各位听众，夜深了。夜班的同志们还在战斗，你们是真正的英雄！",
            "同志们，晚安。好好休息，明天以更大的干劲迎接新的跃进！",
            "听众朋友们，夜深了。大跃进的步伐，日夜不停，分秒必争！",
        ],
    },
}


def bandpass_filter(audio, sample_rate, low_freq, high_freq):
    from scipy.signal import butter, lfilter
    nyq = 0.5 * sample_rate
    low = max(0.001, low_freq / nyq)
    high = min(0.999, high_freq / nyq)
    if low >= high:
        return audio
    b, a = butter(4, [low, high], btype='band')
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


async def gen_one(era, period, variant_idx, text):
    base_name = f"greet_{era}_{period}_{variant_idx:02d}"
    out_wav = os.path.join(OUTPUT_DIR, f"{base_name}.wav")
    out_m4a = os.path.join(OUTPUT_DIR, f"{base_name}.m4a")
    pub_m4a = os.path.join(PUBLIC_DIR, f"{base_name}.m4a")

    if os.path.exists(pub_m4a) and os.path.getsize(pub_m4a) > 3000:
        return True

    tmp_dir = tempfile.gettempdir()
    tmp_mp3 = os.path.join(tmp_dir, f"greet_tts_{base_name}.mp3")

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
    print(f"  ✅ {base_name}.m4a ({duration:.1f}s): {text[:30]}...")
    return True


async def main():
    print("=" * 60)
    print("时光调频 · 年代分组问候语TTS生成器")
    print(f"语速: {SPEED}x  声音: {VOICE}")
    print("3个年代 × 7个时段 × 4个变体 = 84条问候语")
    print("  early (1949-1952): 建国初期语气，庄重")
    print("  mid   (1953-1957): 一五计划语气，建设")
    print("  late  (1958-1960): 大跃进语气，激昂")
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
    for era, periods in GREETINGS.items():
        for period, variants in periods.items():
            for i, text in enumerate(variants, 1):
                tasks.append((era, period, i, text))

    print(f"\n📊 待生成: {len(tasks)} 个问候语音频")
    print()

    success = 0
    fail = 0
    batch = 5

    for i in range(0, len(tasks), batch):
        bt = tasks[i:i + batch]
        coros = [gen_one(era, period, vidx, text) for era, period, vidx, text in bt]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for (era, period, vidx, text), r in zip(bt, results):
            if r is True:
                success += 1
            else:
                fail += 1
                if isinstance(r, Exception):
                    print(f"  ❌ greet_{era}_{period}_{vidx:02d}: {r}")
                else:
                    print(f"  ❌ greet_{era}_{period}_{vidx:02d}")

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(tasks)}, 失败: {fail}")


if __name__ == "__main__":
    asyncio.run(main())
