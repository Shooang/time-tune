#!/usr/bin/env python3
"""
批量生成毛主席诗词朗诵TTS音频（DEMO三段式播音规范版）。
使用 edge-tts 生成语音（zh-CN-YunyangNeural 低沉男声），添加50年代老式广播效果。

播音结构（三段式）：
  ① 栏目引入+导言 → ② 正文朗诵 → ③ 收尾报幕
"""
import asyncio
import os
import sys
import tempfile
import shutil
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "poetry-generated-v2")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.82

INTRO_PREFIX = "中央人民广播电台，现在是文学节目时间。接下来请欣赏毛主席诗词朗诵。"
OUTRO_TEMPLATE = "刚才您听到的是毛主席诗词{title}。"


def clean_poetry_body(text: str) -> str:
    text = text.replace("；", "，").replace(";", "，")
    text = text.replace("？", "。").replace("?", "。")
    text = text.replace("！", "。").replace("!", "。")
    text = text.replace("：", "，").replace(":", "，")
    text = text.replace("……", "。")
    text = text.replace("—", "，")
    text = text.replace("\u201c", "").replace("\u201d", "")
    text = text.replace("\u2018", "").replace("\u2019", "")
    text = text.replace("《", "").replace("》", "")
    return text


def clean_intro_text(text: str) -> str:
    text = text.replace("\u201c", "").replace("\u201d", "")
    text = text.replace("\u2018", "").replace("\u2019", "")
    text = text.replace("《", "").replace("》", "")
    return text


POEMS = [
    {
        "id": "poem_qinyuanchun_xue",
        "title": "沁园春·雪",
        "year": 1945,
        "category": "epic",
        "intro": "沁园春·雪，是毛主席一九三六年二月在陕北东征途中写下的。作品以雄伟的气魄描绘北国雪景，纵论历史英雄，展现了无产阶级革命家的博大胸襟。",
        "text": "北国风光，千里冰封，万里雪飘。望长城内外，惟余莽莽；大河上下，顿失滔滔。山舞银蛇，原驰蜡象，欲与天公试比高。须晴日，看红装素裹，分外妖娆。江山如此多娇，引无数英雄竞折腰。惜秦皇汉武，略输文采；唐宗宋祖，稍逊风骚。一代天骄，成吉思汗，只识弯弓射大雕。俱往矣，数风流人物，还看今朝。",
    },
    {
        "id": "poem_qilu_changzheng",
        "title": "七律·长征",
        "year": 1937,
        "category": "epic",
        "intro": "七律·长征，写于一九三五年十月红军长征胜利到达陕北之时。诗篇生动展现了工农红军跨越万水千山的英雄气概。",
        "text": "红军不怕远征难，万水千山只等闲。五岭逶迤腾细浪，乌蒙磅礴走泥丸。金沙水拍云崖暖，大渡桥横铁索寒。更喜岷山千里雪，三军过后尽开颜。",
    },
    {
        "id": "poem_qinyuanchun_changsha",
        "title": "沁园春·长沙",
        "year": 1925,
        "category": "epic",
        "intro": "沁园春·长沙，是毛主席一九二五年所作。词作描绘湘江秋景，抒发革命青年以天下为己任的豪情壮志。",
        "text": "独立寒秋，湘江北去，橘子洲头。看万山红遍，层林尽染；漫江碧透，百舸争流。鹰击长空，鱼翔浅底，万类霜天竞自由。怅寥廓，问苍茫大地，谁主沉浮？携来百侣曾游，忆往昔峥嵘岁月稠。恰同学少年，风华正茂；书生意气，挥斥方遒。指点江山，激扬文字，粪土当年万户侯。曾记否，到中流击水，浪遏飞舟？",
    },
    {
        "id": "poem_yiqine_loushanguan",
        "title": "忆秦娥·娄山关",
        "year": 1935,
        "category": "military",
        "intro": "忆秦娥·娄山关，是毛主席一九三五年二月在娄山关战斗胜利后写下的。词作雄沉悲壮，表现了红军在激战中从头越的钢铁意志。",
        "text": "西风烈，长空雁叫霜晨月。霜晨月，马蹄声碎，喇叭声咽。雄关漫道真如铁，而今迈步从头越。从头越，苍山如海，残阳如血。",
    },
    {
        "id": "poem_qilu_nanjing",
        "title": "七律·人民解放军占领南京",
        "year": 1949,
        "category": "epic",
        "intro": "七律·人民解放军占领南京，作于一九四九年四月渡江战役胜利之时。诗篇气势磅礴，歌颂了人民解放军追歼残敌、解放全中国的伟大胜利。",
        "text": "钟山风雨起苍黄，百万雄师过大江。虎踞龙盘今胜昔，天翻地覆慨而慷。宜将剩勇追穷寇，不可沽名学霸王。天若有情天亦老，人间正道是沧桑。",
    },
    {
        "id": "poem_langtaosha_beidaihe",
        "title": "浪淘沙·北戴河",
        "year": 1954,
        "category": "construction",
        "intro": "浪淘沙·北戴河，作于一九五四年夏。词人东临碣石，怀古思今，抒发了新中国改天换地的豪迈情怀。",
        "text": "大雨落幽燕，白浪滔天，秦皇岛外打鱼船。一片汪洋都不见，知向谁边？往事越千年，魏武挥鞭，东临碣石有遗篇。萧瑟秋风今又是，换了人间。",
    },
    {
        "id": "poem_shuidiaoge_youyong",
        "title": "水调歌头·游泳",
        "year": 1956,
        "category": "construction",
        "intro": "水调歌头·游泳，写于一九五六年六月。词中描绘了万里长江横渡的壮观景象，展现了新中国建设宏图。",
        "text": "才饮长沙水，又食武昌鱼。万里长江横渡，极目楚天舒。不管风吹浪打，胜似闲庭信步，今日得宽馀。子在川上曰：逝者如斯夫！风樯动，龟蛇静，起宏图。一桥飞架南北，天堑变通途。更立西江石壁，截断巫山云雨，高峡出平湖。神女应无恙，当惊世界殊。",
    },
    {
        "id": "poem_dielianhua_dalishuyi",
        "title": "蝶恋花·答李淑一",
        "year": 1957,
        "category": "lyrical",
        "intro": "蝶恋花·答李淑一，是毛主席一九五七年为怀念革命烈士杨开慧、柳直荀而作。词中运用神话想象，表达了对革命先烈的深切悼念和崇敬之情。",
        "text": "我失骄杨君失柳，杨柳轻飏直上重霄九。问讯吴刚何所有，吴刚捧出桂花酒。寂寞嫦娥舒广袖，万里长空且为忠魂舞。忽报人间曾伏虎，泪飞顿作倾盆雨。",
    },
    {
        "id": "poem_qilu_songwenshen",
        "title": "七律二首·送瘟神 其一",
        "year": 1958,
        "category": "construction",
        "intro": "七律二首·送瘟神，写于一九五八年七月。当毛主席得知余江县消灭了血吸虫病的消息后，欣然提笔写下这两首诗，歌颂了人民群众改天换地的伟大力量。",
        "text": "绿水青山枉自多，华佗无奈小虫何！千村薜荔人遗矢，万户萧疏鬼唱歌。坐地日行八万里，巡天遥看一千河。牛郎欲问瘟神事，一样悲欢逐逝波。",
    },
    {
        "id": "poem_qilu_songwenshen2",
        "title": "七律二首·送瘟神 其二",
        "year": 1958,
        "category": "construction",
        "intro": "七律二首·送瘟神，写于一九五八年七月。当毛主席得知余江县消灭了血吸虫病的消息后，欣然提笔写下这两首诗，歌颂了人民群众改天换地的伟大力量。",
        "text": "春风杨柳万千条，六亿神州尽舜尧。红雨随心翻作浪，青山着意化为桥。天连五岭银锄落，地动三河铁臂摇。借问瘟君欲何往，纸船明烛照天烧。",
    },
    {
        "id": "poem_busuanzi_yongmei",
        "title": "卜算子·咏梅",
        "year": 1961,
        "category": "lyrical",
        "intro": "卜算子·咏梅，是毛主席一九六一年读陆游同题词，反其意而作。词中借梅花不畏严寒的品格，表达了中国共产党人在困难面前坚贞不屈的革命精神。",
        "text": "风雨送春归，飞雪迎春到。已是悬崖百丈冰，犹有花枝俏。俏也不争春，只把春来报。待到山花烂漫时，她在丛中笑。",
    },
    {
        "id": "poem_qilu_daoshaoshan",
        "title": "七律·到韶山",
        "year": 1959,
        "category": "construction",
        "intro": "七律·到韶山，是毛主席一九五九年回到故乡韶山时写下的。诗篇追忆革命斗争岁月，歌颂了新中国农村的新面貌。",
        "text": "别梦依稀咒逝川，故园三十二年前。红旗卷起农奴戟，黑手高悬霸主鞭。为有牺牲多壮志，敢教日月换新天。喜看稻菽千重浪，遍地英雄下夕烟。",
    },
]


def bandpass_filter(audio, sample_rate, low_freq, high_freq):
    from scipy.signal import butter, lfilter
    nyq = 0.5 * sample_rate
    low = max(0.001, low_freq / nyq)
    high = min(0.999, high_freq / nyq)
    if low >= high:
        return audio
    b, a = butter(4, [low, high], btype='band')
    return lfilter(b, a, audio)


def add_distortion(audio, drive=0.12):
    return (2.5 * drive * audio) / (1 + 2 * drive * np.abs(audio))


def generate_pink_noise(n_samples, sample_rate=24000, level=0.004):
    white = np.random.randn(n_samples).astype(np.float32)
    from scipy.signal import butter, lfilter
    b, a = butter(2, 700 / (0.5 * sample_rate), btype='low')
    pink = lfilter(b, a, white)
    pink = pink / np.max(np.abs(pink)) * level
    return pink


def generate_crackle(n_samples, sample_rate=24000, rate=0.0002, level=0.008):
    crackle = np.zeros(n_samples, dtype=np.float32)
    num_crackles = int(n_samples * rate)
    positions = np.random.randint(0, n_samples, num_crackles)
    for pos in positions:
        length = np.random.randint(3, 15)
        end = min(pos + length, n_samples)
        env = np.exp(-np.linspace(0, 4, end - pos))
        crackle[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return crackle


def generate_hum(n_samples, sample_rate=24000, level=0.0015):
    t = np.linspace(0, n_samples / sample_rate, n_samples, dtype=np.float32)
    hum_50 = np.sin(2 * np.pi * 50 * t) * level
    hum_100 = np.sin(2 * np.pi * 100 * t) * level * 0.4
    return hum_50 + hum_100


def apply_vintage_poetry(audio, sample_rate):
    audio = bandpass_filter(audio, sample_rate, 350, 3600)
    audio = add_distortion(audio, 0.12)
    pink = generate_pink_noise(len(audio), sample_rate, 0.004)
    crackle = generate_crackle(len(audio), sample_rate, 0.0002, 0.008)
    hum = generate_hum(len(audio), sample_rate, 0.0015)
    audio = audio + pink + crackle + hum
    fade_len = int(sample_rate * 0.06)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.85
    return audio


def load_audio_mp3(path):
    from scipy.io import wavfile
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        wav_path = path.replace('.mp3', '_temp.wav')
        cmd = [ffmpeg_exe, '-y', '-i', path, '-ar', '24000', '-ac', '1', wav_path]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(wav_path):
            sr, audio = wavfile.read(wav_path)
            os.remove(wav_path)
            return sr, audio.astype(np.float32) / 32768.0
    except Exception as e:
        print(f"   FFmpeg失败: {e}")
    return None, None


def save_audio_wav(audio, sample_rate, path):
    from scipy.io import wavfile
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(path, sample_rate, audio_int16)


async def generate_tts(text, output_path, voice=VOICE, speed=SPEED):
    try:
        import edge_tts
        rate_str = f"+{int((speed-1)*100)}%" if speed > 1 else f"{int((speed-1)*100)}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"   Edge-TTS失败: {e}")
        return False


async def generate_one_poem(poem, force=False):
    pid = poem["id"]
    title = poem["title"]
    raw_text = poem["text"]
    intro = poem["intro"]

    body_text = clean_poetry_body(raw_text)
    intro_clean = clean_intro_text(INTRO_PREFIX + intro)
    title_clean = clean_intro_text(title)
    outro_text = OUTRO_TEMPLATE.format(title=title_clean)

    full_text = f"{intro_clean}。{title_clean}。{body_text}。{outro_text}"

    out_file = f"{pid}.wav"
    out_path = os.path.join(OUTPUT_DIR, out_file)

    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000 and not force:
        print(f"   ⏭️ {pid} 已存在，跳过（使用--force重新生成）")
        return True

    print(f"🎙️ {pid} ({title}) [{poem['category']}]")

    temp_dir = tempfile.gettempdir()
    tts_path = os.path.join(temp_dir, f"poem_tts_{pid}.mp3")

    success = await generate_tts(full_text, tts_path)
    if not success:
        print(f"   ❌ TTS失败")
        return False

    sr, audio = load_audio_mp3(tts_path)
    if sr is None:
        return False

    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage_poetry(audio, sr)
    save_audio_wav(audio, sr, out_path)
    duration = len(audio) / sr
    print(f"   ✅ {out_file} ({duration:.1f}秒)")

    try:
        if os.path.exists(tts_path):
            os.remove(tts_path)
    except:
        pass
    return True


async def main():
    force = "--force" in sys.argv or "-f" in sys.argv
    print("=" * 60)
    print("时光调频 · 毛主席诗词朗诵TTS批量生成器（三段式播音版）")
    print(f"语速: {SPEED}x ({int(SPEED*100)}%)  声音: {VOICE}")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    print(f"\n📜 待生成: {len(POEMS)} 首诗词")
    print(f"📂 输出: {OUTPUT_DIR}")
    if force:
        print("🔄 强制重新生成模式")
    print()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    success = 0
    failed = 0

    batch_size = 3
    for i in range(0, len(POEMS), batch_size):
        batch = POEMS[i:i+batch_size]
        tasks = [generate_one_poem(p, force=force) for p in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                success += 1
            else:
                failed += 1
                if isinstance(r, Exception):
                    print(f"   ❌ 异常: {r}")

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(POEMS)}, 失败: {failed}")

    print(f"\n📋 复制到public目录...")
    copied = 0
    for poem in POEMS:
        src = os.path.join(OUTPUT_DIR, f"{poem['id']}.wav")
        dst = os.path.join(PUBLIC_DIR, f"{poem['id']}.wav")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            copied += 1
    print(f"✅ 已复制 {copied} 个文件到 {PUBLIC_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
