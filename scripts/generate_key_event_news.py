#!/usr/bin/env python3
"""
补充关键历史事件新闻TTS音频。
为重大历史事件月份追加06-08号新闻（每月原01-05为通用新闻）。
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
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "pool-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.88

KEY_EVENTS = [
    {"id": "news_1949_10_06", "year": 1949, "month": 10, "text": "中央人民广播电台，现在是实况广播。同志们！朋友们！今天，一九四九年十月一日，是一个永远值得纪念的日子。天安门广场上，三十万军民聚集在这里，毛泽东主席亲手按动电钮，第一面五星红旗在天安门广场冉冉升起。五十四门礼炮齐鸣二十八响，象征着中国共产党领导中国人民艰苦奋斗二十八年的光辉历程。中国人民从此站起来了！"},
    {"id": "news_1950_06_06", "year": 1950, "month": 6, "text": "新华社平壤二十五日电，朝鲜民主主义人民共和国人民军，已于二十五日拂晓，对李承晚伪军的突然进攻，展开了英勇的自卫反击。朝鲜战争全面爆发。美国总统杜鲁门二十七日发表声明，宣布武装干涉朝鲜内政，并命令第七舰队侵入我国台湾海峡，阻止我人民解放军解放台湾。全国各地人民群众纷纷集会，愤怒声讨美帝国主义的侵略行径。"},
    {"id": "news_1950_10_06", "year": 1950, "month": 10, "text": "同志们！根据朝鲜劳动党和朝鲜民主主义人民共和国政府的请求，根据中国人民的意志，中国人民志愿军在彭德怀司令员率领下，于十月十九日跨过鸭绿江，开赴朝鲜前线，与朝鲜人民军并肩作战，抗击美国侵略者。雄赳赳，气昂昂，跨过鸭绿江。保和平，卫祖国，就是保家乡。全国人民掀起了轰轰烈烈的抗美援朝运动。"},
    {"id": "news_1950_11_06", "year": 1950, "month": 11, "text": "本台消息，中国人民志愿军在朝鲜战场取得第一次战役胜利，歼敌一万五千余人，将敌人从鸭绿江边驱逐到清川江以南，初步稳定了朝鲜战局。与此同时，全国各大城市掀起了轰轰烈烈的抗美援朝保家卫国运动，工人农民纷纷表示要以实际行动支援前线。"},
    {"id": "news_1951_05_06", "year": 1951, "month": 5, "text": "中央台消息，《中央人民政府和西藏地方政府关于和平解放西藏办法的协议》，即十七条协议，于五月二十三日在北京正式签字。西藏和平解放！这是西藏人民从黑暗和痛苦走向光明和幸福的第一步，标志着祖国大陆实现了完全统一。西藏地方政府全权代表阿沛·阿旺晋美等在协议上签字。"},
    {"id": "news_1951_10_06", "year": 1951, "month": 10, "text": "本台消息，中国人民志愿军入朝作战一周年。一年来，志愿军与朝鲜人民军并肩作战，连续进行了五次战役，共歼敌二十三万余人，把敌人从鸭绿江边打回到三八线附近，迫使美方开始停战谈判。全国人民开展了大规模的增产节约运动，支援志愿军，捐献飞机大炮。"},
    {"id": "news_1952_01_06", "year": 1952, "month": 1, "text": "同志们，中共中央发出指示，在全国资本主义工商业者中开展反对行贿、反对偷税漏税、反对盗骗国家财产、反对偷工减料、反对盗窃经济情报的五反运动。此前在党政机关工作人员中开展的反贪污、反浪费、反官僚主义的三反运动正在深入进行。刘青山、张子善特大贪污案已被严肃查处。"},
    {"id": "news_1952_07_06", "year": 1952, "month": 7, "text": "新华社消息，新中国第一条铁路——成渝铁路全线通车。这条铁路全长五百零五公里，完全由中国自己设计、自己施工、使用自己的器材修建。它的建成通车，对于发展西南地区的经济、改善人民生活，具有重大意义。这是新中国成立后铁路建设的第一个重大胜利。"},
    {"id": "news_1952_10_06", "year": 1952, "month": 10, "text": "本台消息，上甘岭战役正在激烈进行中。中国人民志愿军在朝鲜中部的上甘岭地区，以极其英勇顽强的战斗精神，打退了敌人无数次进攻。在仅三点七平方公里的阵地上，敌人倾泻了一百九十多万发炮弹，山头被削低了两米，但志愿军阵地岿然不动。黄继光同志用身体堵住敌人的枪眼，壮烈牺牲。"},
    {"id": "news_1953_07_06", "year": 1953, "month": 7, "text": "特大喜讯！朝鲜停战协定于七月二十七日在板门店正式签署！历时三年多的朝鲜战争终于结束了！中国人民志愿军和朝鲜人民军经过三年浴血奋战，共歼敌一百零九万人，其中美军三十九万人，击落击伤敌机一万二千多架，赢得了抗美援朝战争的伟大胜利！这是世界战争史上以弱胜强的光辉典范。"},
    {"id": "news_1953_12_06", "year": 1953, "month": 12, "text": "同志们，周恩来总理在接见印度代表团时，首次完整地提出了和平共处五项原则：互相尊重主权和领土完整、互不侵犯、互不干涉内政、平等互利、和平共处。这五项原则成为处理国与国之间关系的基本准则，在国际上产生了深远影响。"},
    {"id": "news_1954_09_06", "year": 1954, "month": 9, "text": "中央台消息，第一届全国人民代表大会第一次会议在北京隆重开幕。毛泽东主席致开幕词，他说：我们的总任务是，团结全国人民，争取一切国际朋友的支援，为了建设一个伟大的社会主义国家而奋斗。会议通过了《中华人民共和国宪法》，这是新中国第一部社会主义类型的宪法。毛泽东当选为中华人民共和国主席。"},
    {"id": "news_1954_12_06", "year": 1954, "month": 12, "text": "本台消息，中国人民政治协商会议第二届全国委员会第一次会议召开，一致推举毛泽东为名誉主席，选举周恩来为主席。此前，第二届全国政协已经完成了由代行全国人民代表大会职权到统一战线组织的转变，人民民主统一战线进一步巩固和发展。"},
    {"id": "news_1955_04_06", "year": 1955, "month": 4, "text": "新华社万隆消息，周恩来总理率领中国代表团出席在印度尼西亚万隆举行的亚非会议，即万隆会议。这是历史上第一次由亚非国家自己举行的没有西方殖民国家参加的国际会议。周总理在会上提出求同存异的方针，推动会议取得圆满成功，会议通过了和平共处十项原则。"},
    {"id": "news_1955_09_06", "year": 1955, "month": 9, "text": "本台消息，中华人民共和国主席授予朱德、彭德怀、林彪、刘伯承、贺龙、陈毅、罗荣桓、徐向前、聂荣臻、叶剑英十人中华人民共和国元帅军衔的典礼，于九月二十七日在北京隆重举行。同日，国务院还举行了授予将官军衔的典礼。全军实行军衔制、义务兵役制和薪金制三大制度，标志着人民解放军的正规化现代化建设进入新阶段。"},
    {"id": "news_1955_10_06", "year": 1955, "month": 10, "text": "同志们，新疆维吾尔自治区正式成立！这是新中国成立后建立的第一个省级民族自治区。赛福鼎·艾则孜当选为自治区人民委员会主席。我国各民族平等、团结、互助的新型民族关系进一步巩固和发展，民族区域自治制度显示出强大的生命力。"},
    {"id": "news_1956_01_06", "year": 1956, "month": 1, "text": "新华社消息，中共中央召开关于知识分子问题的会议。周恩来总理在会上作报告，充分肯定知识分子在社会主义建设中的地位和作用，宣布知识分子的绝大部分已经是工人阶级的一部分，并发出了向科学进军的伟大号召。会后，全国掀起了向科学进军的热潮。"},
    {"id": "news_1956_07_06", "year": 1956, "month": 7, "text": "同志们，第一批解放牌汽车在长春第一汽车制造厂试制成功，结束了中国不能制造汽车的历史。当披红挂彩的解放牌汽车缓缓驶下装配线时，全厂工人欢呼雀跃，许多人流下了激动的热泪。从这一天起，中国不能制造汽车的历史一去不复返了！"},
    {"id": "news_1956_09_06", "year": 1956, "month": 9, "text": "中央台消息，中国共产党第八次全国代表大会在北京隆重召开。大会正确分析了国内主要矛盾的变化，指出社会主义制度在我国已经基本建立起来，国内的主要矛盾已经是人民对于经济文化迅速发展的需要同当前经济文化不能满足人民需要的状况之间的矛盾，提出了党和全国人民当前的主要任务是集中力量发展社会生产力。"},
    {"id": "news_1956_12_06", "year": 1956, "month": 12, "text": "本台消息，全国绝大部分地区基本上完成了对农业、手工业和资本主义工商业的社会主义改造。三大改造的基本完成，标志着社会主义公有制在我国已经占据绝对优势地位，社会主义基本制度在我国正式确立，中国从此进入社会主义初级阶段。这是一个伟大的历史性胜利。"},
    {"id": "news_1957_04_06", "year": 1957, "month": 4, "text": "同志们，中共中央发出《关于整风运动的指示》，决定在全党进行一次以正确处理人民内部矛盾为主题，以反对官僚主义、宗派主义和主观主义为内容的整风运动。广大群众和爱国人士积极响应，向党提出了大量有益的批评和建议。"},
    {"id": "news_1957_10_06", "year": 1957, "month": 10, "text": "新华社消息，武汉长江大桥正式通车！这是万里长江上第一座铁路公路两用桥，全长一千六百七十米，连接京汉铁路和粤汉铁路，从此南北天堑变通途。大桥的建成通车，对于连接我国南北交通、促进经济发展具有极为重要的意义。"},
    {"id": "news_1957_11_06", "year": 1957, "month": 11, "text": "同志们，毛泽东主席率领中国代表团赴莫斯科参加十月革命四十周年庆典，并出席社会主义国家共产党和工人党代表会议。毛主席在会上提出了东风压倒西风的著名论断，指出社会主义的力量已经超过了帝国主义的力量。"},
    {"id": "news_1958_05_06", "year": 1958, "month": 5, "text": "中央台消息，中国共产党第八次全国代表大会第二次会议在北京召开。会议正式通过了鼓足干劲、力争上游、多快好省地建设社会主义的总路线。会后，全国各条战线迅速掀起了大跃进的高潮。三面红旗——总路线、大跃进、人民公社开始在全国树立起来。"},
    {"id": "news_1958_08_06", "year": 1958, "month": 8, "text": "本台消息，中共中央政治局在北戴河召开扩大会议，会议决定当年钢产量要比上年翻一番，达到一千零七十万吨，同时通过了《关于在农村建立人民公社问题的决议》。会后，全国迅速形成了全民大炼钢铁和人民公社化运动的高潮。"},
    {"id": "news_1958_10_06", "year": 1958, "month": 10, "text": "同志们，宁夏回族自治区和广西僮族自治区先后宣告成立。我国民族区域自治制度进一步完善。与此同时，全国农村已经基本实现人民公社化，全国七十四万个农业生产合作社合并改组成二万六千多个人民公社，参加公社的农户达到一亿二千多万户，占全国农户总数的百分之九十九以上。"},
    {"id": "news_1959_04_06", "year": 1959, "month": 4, "text": "新华社消息，容国团在第二十五届世界乒乓球锦标赛上，为中国夺得了第一个世界冠军！当容国团战胜匈牙利选手西多，高高举起圣·勃莱德杯的时候，全场响起了热烈的掌声。这是中国体育史上具有里程碑意义的胜利，举国上下为之欢腾。"},
    {"id": "news_1959_09_06", "year": 1959, "month": 9, "text": "本台消息，首都北京的十大建筑即将全部建成，迎接中华人民共和国成立十周年。人民大会堂、中国革命博物馆和中国历史博物馆、中国人民革命军事博物馆、全国农业展览馆、北京火车站、北京工人体育场、民族文化宫、民族饭店、钓鱼台国宾馆、华侨大厦，这十大建筑仅用了十个月时间就建成了，创造了建筑史上的奇迹。"},
    {"id": "news_1959_10_06", "year": 1959, "month": 10, "text": "同志们！今天，我们怀着无比激动的心情，隆重庆祝中华人民共和国成立十周年！十年来，我们的祖国发生了翻天覆地的变化。钢产量从一九四九年的十五万八千吨增长到今年的一千二百万吨，粮食产量达到二亿七千万吨。我们建立了独立的比较完整的工业体系，人民生活水平显著提高。中国人民正在中国共产党的领导下，满怀信心地建设社会主义！"},
    {"id": "news_1959_10_07", "year": 1959, "month": 10, "text": "中央人民广播电台！十年大庆阅兵式现在开始！毛泽东主席、刘少奇主席、周恩来总理等党和国家领导人在天安门城楼上检阅中国人民解放军。受阅部队包括各军兵种的官兵，他们迈着整齐的步伐，威武雄壮地通过天安门广场。新装备的坦克、大炮、喷气式战斗机，展示了人民解放军现代化建设的新成就。"},
    {"id": "news_1960_02_06", "year": 1960, "month": 2, "text": "同志们，大庆石油会战正在黑龙江省萨尔图地区轰轰烈烈地展开。以王进喜为代表的石油工人，头顶蓝天，脚踏荒原，有条件要上，没有条件创造条件也要上，决心摘掉中国贫油的帽子。王进喜同志说：宁可少活二十年，拼命也要拿下大油田。铁人精神正在激励着全国人民。"},
    {"id": "news_1960_04_06", "year": 1960, "month": 4, "text": "新华社消息，郑州黄河大桥建成通车。同时，全国正在开展大规模的技术革新和技术革命运动，工人们创造了许多新的生产方法和工具，生产效率成倍提高。虽然面临一些暂时的困难，但全国人民在党的领导下，自力更生，艰苦奋斗，一定能够战胜前进道路上的一切困难。"},
    {"id": "news_1960_05_06", "year": 1960, "month": 5, "text": "本台消息，中国登山队队员王富洲、贡布、屈银华于五月二十五日凌晨四时二十分，从北坡成功登上了世界最高峰——珠穆朗玛峰！这是人类历史上第一次从北坡征服珠峰，创造了世界登山史上的奇迹。五星红旗插上了地球之巅，全国人民欢欣鼓舞！"},
    {"id": "news_1960_11_06", "year": 1960, "month": 11, "text": "同志们，全国正在广泛开展学习毛泽东著作的群众运动。虽然我们遇到了一些暂时的经济困难，但是中国人民有志气、有能力，在党的领导下，一定能够克服困难，继续前进。自力更生，艰苦奋斗，是我们战胜一切困难的法宝。"},
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


def add_distortion(audio, drive=0.18):
    return (2.5 * drive * audio) / (1 + 2 * drive * np.abs(audio))


def generate_pink_noise(n_samples, sample_rate=24000, level=0.005):
    white = np.random.randn(n_samples).astype(np.float32)
    from scipy.signal import butter, lfilter
    b, a = butter(2, 700 / (0.5 * sample_rate), btype='low')
    pink = lfilter(b, a, white)
    mx = np.max(np.abs(pink))
    if mx > 0:
        pink = pink / mx * level
    return pink


def generate_crackle(n_samples, sample_rate=24000, rate=0.0003, level=0.012):
    crackle = np.zeros(n_samples, dtype=np.float32)
    num_crackles = int(n_samples * rate)
    for _ in range(num_crackles):
        pos = np.random.randint(0, n_samples)
        length = np.random.randint(3, 20)
        end = min(pos + length, n_samples)
        env = np.exp(-np.linspace(0, 4, end - pos))
        crackle[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return crackle


def generate_hum(n_samples, sample_rate=24000, level=0.002):
    t = np.linspace(0, n_samples / sample_rate, n_samples, dtype=np.float32)
    return np.sin(2 * np.pi * 50 * t) * level + np.sin(2 * np.pi * 100 * t) * level * 0.4


def apply_vintage_50s(audio, sample_rate):
    audio = bandpass_filter(audio, sample_rate, 300, 3400)
    audio = add_distortion(audio, 0.15)
    audio = audio + generate_pink_noise(len(audio), sample_rate, 0.005) + generate_crackle(len(audio), sample_rate) + generate_hum(len(audio), sample_rate)
    fade_len = int(sample_rate * 0.04)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    mx = np.max(np.abs(audio))
    if mx > 0:
        audio = audio / mx * 0.9
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
    wavfile.write(path, sample_rate, (audio * 32767).astype(np.int16))


async def generate_tts(text, output_path):
    try:
        import edge_tts
        rate_str = f"+{int((SPEED-1)*100)}%" if SPEED > 1 else f"{int((SPEED-1)*100)}%"
        communicate = edge_tts.Communicate(text, VOICE, rate=rate_str)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"   Edge-TTS失败: {e}")
        return False


async def generate_one_event(seg):
    seg_id = seg["id"]
    text = seg["text"]
    year = seg["year"]
    month = seg["month"]
    out_wav = os.path.join(OUTPUT_DIR, f"{seg_id}.wav")
    out_m4a = os.path.join(OUTPUT_DIR, f"{seg_id}.m4a")
    pub_m4a = os.path.join(PUBLIC_DIR, f"{seg_id}.m4a")

    if os.path.exists(pub_m4a) and os.path.getsize(pub_m4a) > 5000:
        return True
    if os.path.exists(out_m4a) and os.path.getsize(out_m4a) > 5000:
        shutil.copy2(out_m4a, pub_m4a)
        return True

    print(f"🎙️ {seg_id} ({year}年{month}月 关键事件): {text[:40]}...")

    temp_dir = tempfile.gettempdir()
    tts_path = os.path.join(temp_dir, f"keynews_tts_{seg_id}.mp3")

    success = await generate_tts(text, tts_path)
    if not success:
        return False

    sr, audio = load_audio_mp3(tts_path)
    if sr is None:
        return False

    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage_50s(audio, sr)
    save_audio_wav(audio, sr, out_wav)

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

    dur = len(audio) / sr
    print(f"   ✅ {seg_id}.m4a ({dur:.1f}秒)")

    try:
        if os.path.exists(tts_path):
            os.remove(tts_path)
    except:
        pass
    return True


async def main():
    print("=" * 60)
    print("时光调频 · 关键历史事件新闻TTS补充生成器")
    print(f"事件数量: {len(KEY_EVENTS)} 条")
    print("=" * 60)

    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PUBLIC_DIR, exist_ok=True)

    print(f"\n📰 待生成: {len(KEY_EVENTS)} 条关键事件新闻")
    print()

    success = 0
    failed = 0
    batch_size = 5

    for i in range(0, len(KEY_EVENTS), batch_size):
        batch = KEY_EVENTS[i:i+batch_size]
        tasks = [generate_one_event(seg) for seg in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for seg, r in zip(batch, results):
            if r is True:
                success += 1
            else:
                failed += 1
                if isinstance(r, Exception):
                    print(f"  ❌ {seg['id']}: {r}")
                else:
                    print(f"  ❌ {seg['id']}")

    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(KEY_EVENTS)}, 失败: {failed}")

    print(f"\n📋 将关键事件追加到 monthly-news-scripts.json...")
    try:
        with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)

        existing_ids = {n["id"] for n in data["news_briefs"]}
        added = 0
        for evt in KEY_EVENTS:
            if evt["id"] not in existing_ids:
                data["news_briefs"].append({
                    "id": evt["id"],
                    "type": "news_brief_key",
                    "year": evt["year"],
                    "month": evt["month"],
                    "index": int(evt["id"].split("_")[-1]),
                    "text": evt["text"],
                    "title": evt["text"][:50] + "...",
                    "duration": 0,
                    "enterPoints": [0],
                    "signalQuality": 0.88,
                    "volume": 0.85,
                })
                added += 1

        with open(SCRIPTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 追加了 {added} 条新闻到 JSON")
    except Exception as e:
        print(f"⚠️ JSON更新失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
