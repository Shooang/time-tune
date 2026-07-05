#!/usr/bin/env python3
"""
生成1949-1960年每月1条生活片段（共144条），口语化、有温度、有年代感。
"""
import sys, os, json, random, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_base import (
    get_year_data, get_life_scenes_for_year, get_season_scene,
    get_prices_for_year, filter_text
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_LIFE_SNIPPETS = os.path.join(PROJECT_ROOT, "audio-lib", "life-snippets.json")
OUTPUT_AUDIO_POOL = os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool-scripts.json")

CHINESE_NUMS = {0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
               6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}

def arabic_to_chinese_small(text):
    """将文本中10及以下的阿拉伯数字（非价格/计量/日期语境）转为中文数字"""
    result = text
    result = re.sub(r'(?<![\d.])10(?=周年)', '十', result)
    for n in range(1, 10):
        cn = CHINESE_NUMS[n]
        result = re.sub(f'(?<![\\d.]){n}(?=周年)', cn, result)
    def replace_single(m):
        before = m.group(1)
        num = int(m.group(2))
        after = m.group(3)
        if 1 <= num <= 10:
            if after and after[0] in '月日元点.%0123456789':
                return m.group(0)
            if before and before[-1] in '.0123456789':
                return m.group(0)
            return before + CHINESE_NUMS[num] + after
        return m.group(0)
    result = re.sub(r'(^|[^\d.])(10|[1-9])([^\d元角分钱斤尺亩里公里吨米%月日点.]|$)', replace_single, result)
    return result

def normalize_price_spacing(text):
    """移除价格数字与单位之间的多余空格，如'约 0.08 元' -> '大约0.08元'"""
    result = re.sub(r'约\s+', '大约', text)
    result = re.sub(r'(大约)+', '大约', result)
    result = re.sub(r'(\d)\s+([元角分钱斤尺亩])', r'\1\2', result)
    result = re.sub(r'\s+([元角分])', r'\1', result)
    return result

def remove_consecutive_duplicate_sentences(text):
    """移除连续重复的句子"""
    sentences = re.split(r'(?<=[。！？])', text)
    result = []
    prev = None
    for sent in sentences:
        sent_stripped = sent.strip()
        if sent_stripped and sent_stripped == prev:
            continue
        if sent_stripped:
            result.append(sent)
            prev = sent_stripped
    return "".join(result)

def parse_and_format_price(item_name, price_str):
    """
    智能解析并格式化物价条目，处理品牌、工资等特殊格式。
    返回自然中文表述。
    """
    price_str = price_str.strip()
    price_str = re.sub(r'[（(].*?[）)]', '', price_str).strip()
    price_str = price_str.replace('*', '').strip()

    is_per_jin = '/斤' in price_str
    is_per_chi = '/尺' in price_str
    is_per_he = '/盒' in price_str
    price_str = price_str.replace('/斤', '').replace('/尺', '').replace('/盒', '').strip()

    price_str = re.sub(r'(\d)\s+([元角分钱斤尺盒])', r'\1\2', price_str)
    price_str = re.sub(r'约\s*', '大约', price_str)
    price_str = re.sub(r'(大约)+', '大约', price_str)
    price_str = re.sub(r'^大约', '', price_str)
    price_str = re.sub(r'^约', '', price_str)
    price_str = price_str.strip()

    if '-' in price_str and re.search(r'\d+-\d+', price_str):
        price_str = re.sub(r'(\d+)-(\d+)', r'\1到\2', price_str)

    price_val_match = re.search(r'(?:大约)?\s*([\d.]+\s*到\s*[\d.]+|[\d.]+)\s*(个)?(元|斤|工分)', price_str)
    if price_val_match:
        price_val = price_val_match.group(1).replace(' ', '')
        price_unit = price_val_match.group(3)
        measure_word = price_val_match.group(2) or ""
        brand_part = price_str[:price_val_match.start()].strip()
        trailing_part = price_str[price_val_match.end():].strip()
    else:
        price_val_match = re.search(r'(?:大约)?\s*([\d.]+\s*到\s*[\d.]+|[\d.]+)\s*(元|斤|个)', price_str)
        if price_val_match:
            price_val = price_val_match.group(1).replace(' ', '')
            price_unit = price_val_match.group(2)
            measure_word = price_val_match.group(2) if price_val_match.group(2) == "个" else ""
            brand_part = price_str[:price_val_match.start()].strip()
            trailing_part = price_str[price_val_match.end():].strip()
        else:
            return None

    item_display = item_name
    brand = ""
    unit = ""

    if is_per_jin:
        unit = "一斤"
    elif is_per_chi:
        unit = "一尺"
    elif is_per_he:
        unit = "一盒"
    elif price_unit == "斤" and not measure_word:
        unit = "斤"
    elif price_unit == "工分":
        unit = (measure_word or "个") + "工分"
        trailing_part = ""
    elif price_unit == "个":
        trailing_part = ""

    if trailing_part:
        if trailing_part in ["粮票", "布票", "油票"]:
            item_display = trailing_part
        elif item_name in trailing_part:
            item_display = trailing_part

    if brand_part:
        brand_part = brand_part.strip()
        brand_part = re.sub(r'^大约', '', brand_part).strip()
        brand_part = re.sub(r'大约$', '', brand_part).strip()
        brand_part = re.sub(r'元$', '', brand_part).strip()
        brand_part = re.sub(r'斤$', '', brand_part).strip()
        brand_part = re.sub(r'个$', '', brand_part).strip()

        if '工人' in brand_part or '工资' in brand_part or '一级工' in brand_part or '八级工' in brand_part:
            item_display = brand_part
            brand_part = ""
        elif '壮劳力' in brand_part or '一天' in brand_part:
            brand_part = re.sub(r'一个', '', brand_part)
            item_display = brand_part
            brand_part = ""
        elif '每人每月' in brand_part or '每月' in brand_part:
            item_display = brand_part + item_name
            brand_part = ""
        elif '/' in brand_part:
            parts = brand_part.split('/')
            brand = '、'.join(p.strip() for p in parts)
            if not brand.endswith('牌'):
                brand = brand + '牌'
            brand_part = ""
        elif '牌' in brand_part:
            brand = brand_part
            if not brand.endswith('牌') and item_name not in brand:
                brand = brand + '牌'
            brand_part = ""
        elif brand_part and brand_part != item_name and len(brand_part) < 8:
            brand = brand_part
            brand_part = ""

    if brand:
        brand = brand.strip()
        if item_name in brand:
            item_display = brand
        elif brand.endswith('牌'):
            item_display = brand + item_name
        elif brand:
            item_display = brand + '牌' + item_name

    if price_val and price_unit == "元" and '元' not in price_val:
        price_val = price_val + '元'

    if not price_val:
        return None

    if unit:
        return f"{item_display}大约{price_val}{unit}"
    else:
        return f"{item_display}大约{price_val}"

HINDSIGHT_WORDS = {"那时候", "当时", "后来", "众所周知", "遗憾的是"}

OPENING_TEMPLATES = [
    "话说回来，",
    "各位听众，",
    "听众朋友们，",
    "老听众们可能还记得，",
    "最近街头巷尾大家都在说，",
    "要说这段时间啊，",
    "话说最近，",
    "大伙儿知道吗，",
    "同志们，",
    "各位乡亲，",
    "说件有意思的事儿，",
    "给您说个新鲜事儿，",
]

PRICE_OPENINGS = [
    "话说最近的物价啊，",
    "各位听众，给您报一下今天的物价。",
]

SEASON_OPENINGS = [
    "眼下正是{season}，",
    "这段时间啊，",
]

LIFE_KEYWORD_OPENINGS = [
    "听众朋友们，说到{keyword}啊，",
    "老听众们可能还记得，",
    "最近街头巷尾都在说，",
]

CATCHPHRASE_OPENINGS = [
    "现在大家见面都说，",
    "最近最流行的一句话是，",
]

FOOD_OPENINGS = [
    "要说最近吃什么啊，",
    "这段时间，",
]

ENDINGS = [
    "咱们下次再说。",
    "这就是今天的生活点滴。",
    "您说是不是这个理儿？",
    "大伙儿说对不对？",
    "日子就这么一天天过着。",
    "这就是咱们老百姓的日子。",
    "您听听是不是这么回事？",
    "咱们老百姓啊，就盼着日子安稳。",
]

MONTH_SEASON_MAP = {
    1: "寒冬腊月", 2: "残冬初春", 3: "初春时节", 4: "春暖花开", 5: "暮春时分",
    6: "初夏时节", 7: "盛夏三伏", 8: "夏末秋初", 9: "初秋时节", 10: "金秋十月",
    11: "深秋时节", 12: "隆冬腊月",
}

CATCHPHRASES_BY_YEAR = {
    1949: ["中国人民站起来了", "解放了", "天亮了", "新中国成立了"],
    1950: ["抗美援朝，保家卫国", "雄赳赳气昂昂跨过鸭绿江", "最可爱的人", "支援前线"],
    1951: ["三反五反", "增产节约", "支援前线", "打老虎"],
    1952: ["三反五反", "打老虎", "成渝铁路通车了", "增产节约运动"],
    1953: ["一五计划", "和平共处五项原则", "工业化", "建设新中国"],
    1954: ["人代会", "宪法", "日内瓦会议", "人民代表大会"],
    1955: ["万隆会议", "求同存异", "授衔授勋", "十大元帅"],
    1956: ["解放牌汽车", "公私合营", "八大", "社会主义改造"],
    1957: ["武汉长江大桥", "百花齐放百家争鸣", "正确处理人民内部矛盾", "一桥飞架南北"],
    1958: ["总路线、大跃进、人民公社", "鼓足干劲力争上游多快好省", "大炼钢铁", "超英赶美", "吃饭不要钱", "人民公社好"],
    1959: ["容国团世界冠军", "全运会", "十年大庆", "克服暂时困难", "为国争光"],
    1960: ["攀登珠峰", "铁人王进喜", "大庆石油会战", "共渡难关", "为国争光"],
}

FOOD_DESCRIPTIONS = {
    "early_50s": [
        "玉米面窝窝头就着咸菜，喝碗棒子面粥，吃得热乎乎的。虽然粗茶淡饭，能吃饱肚子就知足了",
        "逢年过节才能吃上顿白面饺子，那叫一个香，孩子们都盼着过年这口",
        "大白菜、萝卜是过冬的主菜，家家户户都存着几百斤，地窖里堆得满满当当",
        "工人食堂里的窝窝头、大碴子粥，管够吃，干活的人饭量都大",
        "早上棒子面粥就咸菜疙瘩，中午窝窝头配熬白菜，晚上还是稀粥，日子虽清苦但安稳",
    ],
    "mid_50s": [
        "合作社里供应的粮食够吃，粗细搭配着来，偶尔还能吃上顿白面",
        "星期天改善伙食，买点猪肉炖上粉条，再蒸上一锅白馒头，一家人吃得美滋滋",
        "菜市场里青菜、萝卜、白菜样样有，按季节供应，价钱也便宜",
        "单位食堂的菜便宜，几分钱就能买份素菜，一毛钱就能吃个肉菜",
        "粮食定量供应，大家精打细算着过日子，粗细粮搭配着吃，营养也够",
    ],
    "late_50s": [
        "公共食堂里吃饭不要钱，大白馒头管够，红烧肉炖得香，大伙儿敞开肚皮吃",
        "人民公社的大食堂，大伙儿围在一起吃饭，热闹得很，像个大家庭",
        "大炼钢铁那会儿，家家户户把铁锅都献出去了，都在食堂吃饭，干活也在一起",
        "新米下来的时候，煮上一锅白米饭，就着炖菜，香气飘满整个村子",
        "食堂里饭菜花样多，蒸馒头、熬大锅菜，男女老少都在一起吃，干劲十足",
    ],
    "hardship": [
        "大家想办法克服困难，粗粮细做，瓜菜代粮，邻里之间互相帮衬着共渡难关",
        "各级政府关心群众生活，想办法安排好大家的吃穿用度，保证基本供应",
        "邻里之间互相帮衬，有什么好吃的都拿出来分享，大家心齐就没有过不去的坎",
        "大家齐心协力，勤俭节约，一定能克服眼前的暂时困难，日子会好起来的",
    ],
}

DAILY_LIFE_DETAILS = {
    1949: [
        "大街上到处都是欢庆解放的人群，扭秧歌的、打腰鼓的，热闹非凡",
        "老百姓们都在盼着新中国成立，盼着以后能过上安稳日子",
        "解放军进了城，不拿群众一针一线，大家都说这是人民自己的队伍",
    ],
    1950: [
        "家家户户都在给志愿军做干粮、缝棉衣，母亲送儿子、妻子送丈夫参军",
        "工人们加班加点生产物资支援前线，农民们多打粮食支援国家",
        "大街上随处可见抗美援朝的标语，大家捐款捐物，支援前线打美帝",
    ],
    1951: [
        "三反运动开展起来了，大家都在检举贪污浪费行为，风气为之一新",
        "工人们开展增产节约运动，多生产产品支援国家建设和前线",
        "农村里开始组织互助组，几家几户凑在一起干活，效率提高不少",
    ],
    1952: [
        "成渝铁路通车了，四川人民盼了几十年的铁路终于修通了，大家都很高兴",
        "五反运动在全国开展，打击不法资本家的违法行为，稳定市场物价",
        "各地都在开展爱国卫生运动，打扫卫生、消灭四害，预防疾病",
    ],
    1953: [
        "第一个五年计划开始了，全国人民干劲十足，要为实现工业化而奋斗",
        "街上到处都是建设国家的标语，工人农民都在努力生产，建设新中国",
        "粮食开始实行统购统销，大家凭粮票买粮，保障供应稳定",
    ],
    1954: [
        "第一次全国人民代表大会召开了，人民开始当家作主，参与国家大事",
        "新中国第一部宪法颁布了，大家都在学习讨论，说这是人民的宪法",
        "日内瓦会议上周恩来总理展现了大国风范，中国人在国际上有了地位",
    ],
    1955: [
        "万隆会议上周总理提出求同存异方针，亚非国家都佩服中国的外交智慧",
        "解放军授衔授勋典礼举行，十大元帅十大将，大家都为这些战斗英雄感到骄傲",
        "街上流行穿列宁装、布拉吉，年轻人都追求进步，积极向上",
    ],
    1956: [
        "长春一汽生产出第一批解放牌汽车，大街上人们都围着看，中国自己造汽车了",
        "社会主义改造基本完成，公私合营了，工商业者也都成了社会主义劳动者",
        "八大召开了，指出国内主要矛盾是人民对于经济文化发展的需要",
    ],
    1957: [
        "武汉长江大桥建成通车了，一桥飞架南北，天堑变通途，大家都去看",
        "整风运动开始，大家都在给党提意见，帮助党改进工作作风",
        "市面上物资丰富，物价稳定，老百姓的日子比前几年好过了不少",
    ],
    1958: [
        "总路线公布了，鼓足干劲、力争上游、多快好省地建设社会主义，大家干劲十足",
        "人民公社化运动开展起来了，农村都办起了人民公社，吃饭不要钱",
        "大炼钢铁运动热火朝天，男女老少齐上阵，小高炉遍地开花，超英赶美",
    ],
    1959: [
        "容国团拿了世界冠军，这是中国第一个世界冠军，全国人民都欢欣鼓舞",
        "第一届全运会在北京举行，运动员们奋力拼搏，展现新中国人民的精神面貌",
        "建国十周年大庆，首都北京举行了盛大的庆祝活动，十年建设成就辉煌",
    ],
    1960: [
        "中国登山队登上了珠穆朗玛峰，人类第一次从北坡登顶，为祖国争了光",
        "大庆石油会战开始了，铁人王进喜带领工人们日夜奋战，要甩掉贫油帽子",
        "大家都在学习愚公移山的精神，艰苦奋斗，克服眼前的困难，建设祖国",
    ],
}


def simple_clean_text(text, year):
    if not text:
        return ""
    result = text
    result = result.replace("——", "")
    result = re.sub(r"[~～]+", "", result)
    for word in HINDSIGHT_WORDS:
        result = result.replace(word, "")
    if 1949 <= year <= 1960:
        if not (1950 <= year <= 1953):
            result = result.replace("美帝国主义", "美国")
            result = result.replace("美帝", "美国")
        hardship_replacements = [
            (r"粮食不够吃", "大家想办法克服困难"),
            (r"吃糠咽菜", "大家想办法共渡难关"),
            (r"粮票不够", "供应有保障"),
            (r"饿(死|肚子|得)", ""),
            (r"饥饿", ""),
            (r"饥荒", "遇到暂时困难"),
        ]
        for pat, repl in hardship_replacements:
            result = re.sub(pat, repl, result)
    if year < 1958:
        result = result.replace("社员们", "老百姓")
        result = result.replace("社员同志", "乡亲们")
    result = re.sub(r"\d{1,2}月\d{1,2}日[——\-—\s]*", "", result)
    result = re.sub(r"^[\s，,。]+", "", result)
    result = re.sub(r'([。！？])\1+', r'\1', result)
    result = re.sub(r'[，,]{2,}', '，', result)
    result = re.sub(r'\s+', ' ', result)
    return result.strip()


def remove_future_year_sentences(text, current_year):
    sentences = re.split(r'(?<=[。！？])', text)
    kept = []
    hindsight_keywords = {"此后", "后来", "至今", "为以后", "为今后", "陆续与", "又陆续", "为后来"}
    for s in sentences:
        s_stripped = s.strip()
        if not s_stripped:
            continue
        has_future = False
        years_found = re.findall(r'(\d{4})年', s_stripped)
        for y_str in years_found:
            try:
                y = int(y_str)
                if 1900 <= y <= 2100 and y > current_year:
                    has_future = True
                    break
            except ValueError:
                pass
        if not has_future:
            for kw in hindsight_keywords:
                if kw in s_stripped:
                    has_future = True
                    break
        if not has_future:
            kept.append(s)
    return "".join(kept)


def deduplicate_phrases(text):
    for _ in range(3):
        changed = False
        for n in [6, 5, 4, 3]:
            for i in range(len(text) - n * 2):
                phrase = text[i:i + n]
                if len(re.sub(r'[^\u4e00-\u9fa5]', '', phrase)) < 2:
                    continue
                if text[i + n:i + n * 2] == phrase:
                    text = text[:i + n] + text[i + n * 2:]
                    changed = True
                    break
            if changed:
                break
        if not changed:
            break
    text = re.sub(r'(化运动)化运动', r'\1', text)
    text = re.sub(r'(人民公社)人民公社', r'\1', text)
    text = re.sub(r'(农村)农村', r'\1', text)
    return text


def filter_era_inappropriate(text, year):
    anachronisms = [
        (r'《地道战》', 1965),
        (r'《地雷战》', 1962),
        (r'《南征北战》', 1952),
        (r'雷锋', 1963),
        (r'向雷锋同志学习', 1963),
        (r'文化大革命', 1966),
        (r'红卫兵', 1966),
        (r'上山下乡', 1968),
        (r'知青', 1968),
    ]
    for pat, min_year in anachronisms:
        if year < min_year:
            text = re.sub(pat, '', text)
    text = re.sub(r'[，、；：]\s*[。！？]', '。', text)
    text = re.sub(r'^[《》"\'「」、，。；：\s]+', '', text)
    text = re.sub(r'《》', '', text)
    text = re.sub(r'、\s*[、，。]', '、', text)
    return text


def clean_broadcast_text(text, year):
    if not text:
        return ""
    text = filter_era_inappropriate(text, year)
    text = simple_clean_text(text, year)
    text = remove_future_year_sentences(text, year)
    text = re.sub(r'([。！？])\1+', r'\1', text)
    text = re.sub(r'[，,]{2,}', '，', text)
    text = deduplicate_phrases(text)
    text = filter_text(text, year, keep_era_terms=True)
    if not text:
        return ""
    text = re.sub(r'约\s*约\s*', '约', text)
    text = re.sub(r'大约\s*约\s*', '大约', text)
    text = deduplicate_phrases(text)
    text = re.sub(r'[，、]\s*[。！？]', '。', text)
    text = re.sub(r'[，；：、]\s*[，；：、]', '，', text)
    text = re.sub(r'[。]{2,}', '。', text)
    text = re.sub(r'[，]{2,}', '，', text)
    text = re.sub(r'^[，、；：。\s]+', '', text)
    text = re.sub(r'\s+', '', text)
    if text[-1] not in "。！？":
        text = text + "。"
    return text.strip()


def money_to_spoken(price_str):
    m = re.match(r'^([\d.]+)\s*元$', price_str.strip())
    if m:
        val = float(m.group(1))
        if val < 0.1:
            fen = int(round(val * 100))
            return f"{fen}分钱"
        elif val < 1:
            jiao = int(round(val * 10))
            fen = int(round((val * 10 - jiao) * 10))
            if fen > 0:
                return f"{jiao}角{fen}分钱"
            return f"{jiao}毛钱"
        else:
            yuan = int(val)
            jiao = int(round((val - yuan) * 10))
            if jiao > 0:
                return f"{yuan}块{jiao}毛钱"
            return f"{yuan}块钱"
    return price_str


def format_price_phrase(item_name, price_str):
    price_str = price_str.strip().replace("*", "").strip()
    if item_name in price_str and len(price_str) > len(item_name) + 3:
        return price_str
    price_str = re.sub(r'^约\s*', '', price_str)
    price_str = re.sub(r'^大约\s*', '', price_str)
    if price_str.endswith('/斤'):
        price_val = price_str[:-3].strip()
        spoken = money_to_spoken(price_val + "元") if re.match(r'^[\d.]+$', price_val) else price_val
        return f"{item_name}{spoken}一斤"
    else:
        if any(kw in item_name for kw in ["工资", "自行车", "手表", "缝纫机"]):
            return f"{item_name}{price_str}"
        spoken = money_to_spoken(price_str) if re.match(r'^[\d.]+\s*元$', price_str) else price_str
        return f"{item_name}{spoken}"


def get_people_word(rng, year):
    if 1959 <= year <= 1961:
        return "大家"
    if year < 1958:
        return rng.choice(["老百姓", "乡亲们", "工人们", "农民们"])
    else:
        return rng.choice(["社员们", "老百姓", "同志们", "社员同志们"])


def generate_price_snippet(rng, year, month, prices):
    opening_template = rng.choice(PRICE_OPENINGS)
    price_items = list(prices.items())
    rng.shuffle(price_items)
    selected = price_items[:rng.randint(2, 3)]
    price_parts = []
    used_phrases = set()
    for item, price_str in selected:
        phrase = parse_and_format_price(item, price_str)
        if phrase and phrase not in used_phrases:
            price_parts.append(phrase)
            used_phrases.add(phrase)
    price_text = "，".join(price_parts)
    people_word = get_people_word(rng, year)
    daily_life = rng.choice(DAILY_LIFE_DETAILS.get(year, [
        f"{people_word}精打细算着过日子，物价稳定心里就踏实",
        f"这点钱啊，{people_word}得算计着花，一分钱掰成两半花",
        f"物价稳定，{people_word}的日子就过得安稳",
    ]))
    extra = rng.choice([
        f"{people_word}过日子，精打细算着来。{daily_life}",
        f"这点钱啊，{people_word}得算计着花。{daily_life}",
        f"物价稳定，{people_word}的心里就踏实。{daily_life}",
        daily_life,
    ])
    ending = rng.choice(ENDINGS)
    text = f"{opening_template}{price_text}。{extra}。{ending}"
    return clean_broadcast_text(text, year)


def generate_season_snippet(rng, year, month, season_scene):
    season_name = MONTH_SEASON_MAP.get(month, "时节")
    opening = rng.choice(SEASON_OPENINGS).format(season=season_name)
    people_word = get_people_word(rng, year)
    activities_by_month = {
        1: [
            f"天寒地冻的，{people_word}趁着农闲在家积肥、修农具，准备开春的农活",
            "快过年了，家家户户都在扫房子、蒸年糕、准备年货，孩子们盼着穿新衣、放鞭炮",
            "外面刮着西北风，屋里烧着热炕头，一家人围在一起包饺子，暖和和的",
        ],
        2: [
            "立春了，天气渐渐转暖，河边上的柳树开始冒芽了，春天快要来了",
            f"{people_word}开始准备春耕，收拾农具、选种子，就等天气暖和了下地",
            "元宵节前后，街上有耍龙灯、舞狮子的，到处都是过年的热闹气氛",
        ],
        3: [
            f"春耕开始了，{people_word}都在地里忙着翻地、播种，一年之计在于春",
            "桃花开了，柳树绿了，燕子从南方飞回来了，到处都是生机勃勃的样子",
            "天气暖和了，大人小孩都脱掉了厚棉袄，换上了夹衣，身上轻快多了",
        ],
        4: [
            "春光明媚，田里的麦苗返青了，油菜花也开了，一片金黄，好看得很",
            f"{people_word}忙着春种春管，浇水施肥，盼着今年有个好收成",
            "春雨贵如油，下一场春雨，庄稼就窜一截，大家心里都高兴",
        ],
        5: [
            f"暮春时分，天气不冷不热，{people_word}在地里忙活，一年的收成就看这时候了",
            "槐花开了，满街都是香气，孩子们捋槐花回家蒸着吃，香甜得很",
            "马上就要麦收了，大家都在准备镰刀、麦场，就等麦子熟了开镰",
        ],
        6: [
            f"初夏时节，麦子熟了，{people_word}忙着夏收夏种，龙口夺粮，一刻也耽误不得",
            "天开始热了，知了在树上叫起来了，中午时分大家都在树荫下歇凉",
            "麦子收完了，紧接着就要种秋庄稼，大家起早贪黑地忙活",
        ],
        7: [
            f"盛夏三伏，天热得像蒸笼，{people_word}趁着早晚凉快在地里干活，中午歇晌",
            "午后常常下一场雷阵雨，雨过天晴，空气凉快多了，有时候还能看到彩虹",
            "知了在树上使劲叫，大人们摇着蒲扇在大树底下歇凉，孩子们在河里洗澡摸鱼",
        ],
        8: [
            f"夏末秋初，天气还是有点热，但早晚已经凉快了，{people_word}忙着给秋庄稼施肥",
            "玉米抽穗了，高粱红了，眼看着秋天就要到了，庄稼长势不错",
            "放暑假了，孩子们帮家里放牛、割草，或者在河里玩水，日子过得快活",
        ],
        9: [
            f"秋收开始了，{people_word}忙着收割玉米、高粱，地里一片热火朝天的景象",
            "秋高气爽，蓝天白云，天气不冷不热，正是干活的好时候",
            "秋收秋种连在一起，收完秋庄稼紧接着就要种冬小麦，大家都在抢农时",
        ],
        10: [
            "金秋十月，秋庄稼都收完了，场上堆着金黄的玉米、火红的高粱，一派丰收景象",
            "天气凉了，树叶开始黄了，秋风一吹，叶子飘下来，地上铺了一层",
            f"{people_word}忙着秋耕、种冬小麦，为来年的收成打基础",
        ],
        11: [
            f"深秋时节，天气冷了，{people_word}把粮食入仓、蔬菜入窖，准备过冬",
            "大雁往南飞了，夜里开始上冻了，早上起来地上一层白霜",
            "地里的活差不多干完了，大家开始搞农田水利建设，修梯田、挖水渠",
        ],
        12: [
            "隆冬腊月，天寒地冻，地里没什么活了，大家在家搞副业、积肥，准备过年",
            "开始下雪了，大地一片白茫茫，孩子们在雪地里堆雪人、打雪仗，玩得高兴",
            "快到年底了，家家户户都在置办年货，杀猪宰羊，准备过个热闹年",
        ],
    }
    season_key = "spring" if month in [3,4,5] else "summer" if month in [6,7,8] else "autumn" if month in [9,10,11] else "winter"
    default_activities = {
        "spring": [f"{people_word}都在地里忙着春耕，准备播种，到处都是热火朝天的景象"],
        "summer": [f"天热得很，{people_word}趁着早晚凉快在地里干活，中午歇晌"],
        "autumn": [f"秋收的季节到了，{people_word}忙着收割庄稼，一派丰收景象"],
        "winter": [f"天寒地冻的，{people_word}趁着农闲积肥修水利，为来年做准备"],
    }
    activities = activities_by_month.get(month, default_activities[season_key])
    activity = rng.choice(activities)
    ending = rng.choice(ENDINGS)
    scene_text = season_scene if season_scene else ""
    if scene_text:
        scene_text = scene_text.rstrip("。") + "。"
    text = f"{opening}{scene_text}{activity}。{ending}"
    return clean_broadcast_text(text, year)


def is_valid_memory_point(mp, year):
    if not mp:
        return False
    anachronisms = [
        ('地道战', 1965), ('地雷战', 1962), ('雷锋', 1963),
        ('文化大革命', 1966), ('红卫兵', 1966), ('知青', 1968),
    ]
    for kw, min_year in anachronisms:
        if kw in mp and year < min_year:
            return False
    if len(mp) < 4:
        return False
    if re.match(r'^[、，《》\s]+$', mp):
        return False
    return True


def generate_life_keyword_snippet(rng, year, month, life_scenes, year_data):
    appropriate = []
    late_50s_scenes = {"人民公社", "大跃进", "大炼钢铁", "公共食堂"}
    for scene in life_scenes:
        name = scene.get('name', '')
        scene_text = scene.get('scene', '')
        combined = name + scene_text
        if year < 1958 and any(kw in combined for kw in late_50s_scenes):
            continue
        appropriate.append(scene)
    if not appropriate:
        keyword = year_data.get('key_event', '建设新中国')
        middle = f"大家都在积极投身{keyword}，干劲十足"
    else:
        chosen = rng.choice(appropriate)
        keyword = chosen.get('name', '过日子')
        memory_points = [mp for mp in chosen.get('memory_points', []) if is_valid_memory_point(mp, year)]
        scene_desc = chosen.get('scene', '')
        if memory_points and rng.random() < 0.4:
            mp = rng.choice(memory_points)
            middle = f"{scene_desc}。{mp}，都是让人难忘的记忆"
        else:
            middle = scene_desc
    opening_template = rng.choice(LIFE_KEYWORD_OPENINGS).format(keyword=keyword)
    people_word = get_people_word(rng, year)
    daily_life = rng.choice(DAILY_LIFE_DETAILS.get(year, [
        f"{people_word}的日子越过越有奔头",
        f"到处都是一片欣欣向荣的景象",
        f"大家齐心协力建设新中国",
    ]))
    extra = rng.choice([
        f"{people_word}都参与进来了，热闹得很。{daily_life}",
        f"这可是{people_word}生活里的一件大事。{daily_life}",
        f"{people_word}都说这日子越来越有奔头。{daily_life}",
        daily_life,
    ])
    ending = rng.choice(ENDINGS)
    text = f"{opening_template}{middle}。{extra}。{ending}"
    return clean_broadcast_text(text, year)


def generate_catchphrase_snippet(rng, year, month):
    phrases = CATCHPHRASES_BY_YEAR.get(year, ["建设新中国", "努力生产"])
    phrase = rng.choice(phrases)
    opening = rng.choice(CATCHPHRASE_OPENINGS)
    people_word = get_people_word(rng, year)
    daily_life = rng.choice(DAILY_LIFE_DETAILS.get(year, [
        f"这句话鼓舞着{people_word}努力生产建设祖国",
        f"{people_word}干劲十足，建设社会主义新中国",
        f"到处都是热火朝天的建设场面",
    ]))
    reactions = [
        f"{people_word}嘴上都挂着这句话，干活都更有劲儿了，早也干晚也干，就想着为国家多出力",
        f"走到哪儿都能听到{people_word}这么说，工厂里、农村里、学校里，到处都是这句话",
        f"{people_word}都说这句话说到心坎里了，照着这句话去做，日子就有奔头",
        f"这句话鼓舞着{people_word}努力生产、建设祖国，再苦再累心里也甜",
    ]
    reaction = rng.choice(reactions)
    ending = rng.choice(ENDINGS)
    text = f"{opening}「{phrase}」。{reaction}。{daily_life}。{ending}"
    return clean_broadcast_text(text, year)


def generate_food_snippet(rng, year, month):
    opening = rng.choice(FOOD_OPENINGS)
    if 1959 <= year <= 1961:
        food_pool = FOOD_DESCRIPTIONS["hardship"]
    elif year >= 1958:
        food_pool = FOOD_DESCRIPTIONS["late_50s"]
    elif year >= 1955:
        food_pool = FOOD_DESCRIPTIONS["mid_50s"]
    else:
        food_pool = FOOD_DESCRIPTIONS["early_50s"]
    food_desc = rng.choice(food_pool)
    people_word = get_people_word(rng, year)
    daily_life = rng.choice(DAILY_LIFE_DETAILS.get(year, [
        f"{people_word}的日子虽说不富裕，但能吃饱穿暖就知足了",
        f"民以食为天，{people_word}最盼的就是锅里有粮、心里不慌",
        f"一日三餐虽然简单，但一家人围在一起吃饭，就是最大的幸福",
    ]))
    ending = rng.choice(ENDINGS)
    text = f"{opening}{food_desc}。{daily_life}。{ending}"
    return clean_broadcast_text(text, year)


def select_snippet_type(rng, year, month, prices, life_scenes, season_scene):
    type_order = ["price", "season", "life_keyword", "catchphrase", "food"]
    weights = [0.25, 0.25, 0.30, 0.10, 0.10]
    available = []
    available_weights = []
    available_types = []
    if prices:
        available.append("price")
        available_weights.append(weights[0])
    if season_scene:
        available.append("season")
        available_weights.append(weights[1])
    if life_scenes:
        available.append("life_keyword")
        available_weights.append(weights[2])
    available.append("catchphrase")
    available_weights.append(weights[3])
    available.append("food")
    available_weights.append(weights[4])
    total_weight = sum(available_weights)
    normalized_weights = [w / total_weight for w in available_weights]
    r = rng.random()
    cumulative = 0
    for t, w in zip(available, normalized_weights):
        cumulative += w
        if r < cumulative:
            return t
    return available[-1]


def generate_fallback_snippet(rng, year, month):
    """生成兜底的生活片段，确保长度足够"""
    people_word = "社员们" if year >= 1958 else "老百姓"
    month_scene = {
        1: "天寒地冻的腊月", 2: "快要过年的时候", 3: "春耕开始", 4: "春光明媚",
        5: "快要麦收", 6: "夏收夏种", 7: "盛夏三伏", 8: "夏末秋初",
        9: "秋收大忙", 10: "金秋十月", 11: "秋耕冬修", 12: "隆冬腊月",
    }
    scene = month_scene.get(month, "这段时间")
    texts = [
        f"各位听众，{scene}，{people_word}都在忙着手里的活计。日子虽说不算富裕，但能吃饱穿暖，一家人平平安安的，比什么都强。大伙儿勤勤恳恳地干活，建设咱们的新中国。这就是咱们老百姓的日子。",
        f"同志们，{scene}，工厂里机器轰鸣，工人们干劲十足地生产；田地里庄稼长势不错，{people_word}精心侍弄着。物价稳定，供应充足，大家的日子过得安稳踏实。咱们老百姓啊，就盼着日子安稳。",
    ]
    return rng.choice(texts)

def generate_one_snippet(year, month):
    rng = random.Random(f"life_{year}_{month}")
    prices = get_prices_for_year(year)
    life_scenes = get_life_scenes_for_year(year)
    season_scene = get_season_scene(month, variant=(year + month) % 4, year=year)
    year_data = get_year_data(year)
    stype = select_snippet_type(rng, year, month, prices, life_scenes, season_scene)
    text = ""
    type_order = ["price", "season", "life_keyword", "catchphrase", "food"]
    for attempt in range(8):
        current_type = type_order[attempt % len(type_order)]
        if current_type == "price" and prices:
            text = generate_price_snippet(rng, year, month, prices)
        elif current_type == "season" and season_scene:
            text = generate_season_snippet(rng, year, month, season_scene)
        elif current_type == "life_keyword":
            text = generate_life_keyword_snippet(rng, year, month, life_scenes, year_data)
        elif current_type == "catchphrase":
            text = generate_catchphrase_snippet(rng, year, month)
        else:
            text = generate_food_snippet(rng, year, month)
        if text and len(text) >= 80:
            stype = current_type
            break
    if not text or len(text) < 80:
        text = generate_fallback_snippet(rng, year, month)
        stype = "life_keyword"
    text = normalize_price_spacing(text)
    text = remove_consecutive_duplicate_sentences(text)
    text = arabic_to_chinese_small(text)
    text = re.sub(r'\s+', '', text)
    char_count = len(re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text))
    duration = round(char_count / 3.5)
    duration = max(8, min(25, duration))
    signal_quality = round(0.82 + rng.random() * 0.12, 2)
    volume = round(0.78 + rng.random() * 0.10, 2)
    return {
        "id": f"life_{year}_{month:02d}",
        "type": "life_snippet",
        "year": year,
        "month": month,
        "text": text,
        "duration": duration,
        "signalQuality": signal_quality,
        "volume": volume,
    }, stype


def main():
    print("正在加载知识库...")
    life_snippets = []
    type_counts = {
        "price": 0,
        "season": 0,
        "life_keyword": 0,
        "catchphrase": 0,
        "food": 0,
    }
    total_chars = 0
    format_errors = 0
    type_names = {
        "price": "物价小播报",
        "season": "时令季节",
        "life_keyword": "生活记忆",
        "catchphrase": "流行语",
        "food": "美食日常",
    }
    for year in range(1949, 1961):
        for month in range(1, 13):
            snippet, stype = generate_one_snippet(year, month)
            life_snippets.append(snippet)
            type_counts[stype] = type_counts.get(stype, 0) + 1
            total_chars += len(snippet["text"])
            if "。。" in snippet["text"] or "！！" in snippet["text"]:
                format_errors += 1
    output = {
        "_meta": {
            "version": "1.0",
            "demo_range": "1949-1960",
            "coverage": "每月1条生活片段，共144条",
            "created_at": "2026-06-30",
            "note": "从知识库的物价、季节、生活关键词生成的生活片段，口语化有年代感。"
        },
        "life_snippets": life_snippets
    }
    os.makedirs(os.path.dirname(OUTPUT_LIFE_SNIPPETS), exist_ok=True)
    with open(OUTPUT_LIFE_SNIPPETS, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ life-snippets.json 已保存到: {OUTPUT_LIFE_SNIPPETS}")
    with open(OUTPUT_AUDIO_POOL, 'r', encoding='utf-8') as f:
        audio_pool = json.load(f)
    audio_pool["life_snippets"] = life_snippets
    with open(OUTPUT_AUDIO_POOL, 'w', encoding='utf-8') as f:
        json.dump(audio_pool, f, ensure_ascii=False, indent=2)
    print(f"✅ audio-pool-scripts.json 已更新: {OUTPUT_AUDIO_POOL}")
    print("\n" + "=" * 70)
    print("📊 生成统计")
    print("=" * 70)
    print(f"📅 总共生成: {len(life_snippets)} 条生活片段")
    print(f"📝 平均字数: {total_chars // len(life_snippets)} 字")
    print(f"⚠️  格式错误数: {format_errors}")
    print()
    print("📋 各类型分布:")
    for t, name in type_names.items():
        cnt = type_counts.get(t, 0)
        pct = cnt * 100 // len(life_snippets)
        print(f"  - {name}: {cnt} 条 ({pct}%)")
    print()
    print("=" * 70)
    print("📻 示例片段（5条）")
    print("=" * 70)
    sample_keys = [
        (1949, 1, "1949-01"),
        (1950, 10, "1950-10"),
        (1955, 5, "1955-05"),
        (1958, 8, "1958-08"),
        (1960, 7, "1960-07"),
    ]
    snippet_map = {(s["year"], s["month"]): s for s in life_snippets}
    for y, m, label in sample_keys:
        s = snippet_map.get((y, m))
        if s:
            print(f"\n【{label}】 id={s['id']} | 时长≈{s['duration']}秒 | 字数={len(s['text'])}")
            print(f"  {s['text']}")
    print()
    print("=" * 70)
    print("🔍 验证检查")
    print("=" * 70)
    pre_1958_sheyuan = 0
    for s in life_snippets:
        if s["year"] < 1958 and "社员" in s["text"]:
            pre_1958_sheyuan += 1
            print(f"⚠️  {s['id']} 发现1958年前有'社员': {s['text'][:50]}...")
    print(f"  - 1958年前'社员'出现次数: {pre_1958_sheyuan} {'✅ 通过' if pre_1958_sheyuan == 0 else '❌ 有问题'}")
    double_period = 0
    for s in life_snippets:
        if "。。" in s["text"]:
            double_period += 1
    print(f"  - 双句号问题: {double_period} {'✅ 通过' if double_period == 0 else '❌ 有问题'}")
    duplicate_price = 0
    for s in life_snippets:
        if "买一斤" in s["text"] and "一斤" in s["text"][:s["text"].index("买一斤")]:
            duplicate_price += 1
            print(f"⚠️  {s['id']} 物价表述重复: {s['text'][:60]}...")
    print(f"  - 物价重复表述: {duplicate_price} {'✅ 通过' if duplicate_price == 0 else '❌ 有问题'}")
    too_short = 0
    too_long = 0
    for s in life_snippets:
        if len(s["text"]) < 80:
            too_short += 1
        if len(s["text"]) > 250:
            too_long += 1
    print(f"  - 字数<80: {too_short}, 字数>250: {too_long}")
    hindsight_found = 0
    for s in life_snippets:
        for kw in ["后来", "那时候", "众所周知", "回首"]:
            if kw in s["text"]:
                hindsight_found += 1
                print(f"⚠️  {s['id']} 发现后见之明词'{kw}': {s['text'][:60]}...")
                break
    print(f"  - 后见之明词: {hindsight_found} {'✅ 通过' if hindsight_found == 0 else '❌ 有问题'}")
    meidi_checked = True
    for s in life_snippets:
        if s["year"] in [1950, 1951, 1952, 1953]:
            pass
        else:
            if "美帝" in s["text"] or "美帝国主义" in s["text"]:
                print(f"⚠️  {s['id']} 非抗美援朝时期不应有'美帝': {s['text'][:60]}...")
                meidi_checked = False
    print(f"  - '美帝'仅在抗美援朝时期使用: {'✅ 通过' if meidi_checked else '❌ 有问题'}")
    print()
    print("=" * 70)
    print("✅ 全部完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()
