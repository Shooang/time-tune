#!/usr/bin/env python3
"""
从知识库和数据库提取1949-1960年每月关键事件，生成每月6-8条有温度的广播稿新闻。
"""
import sqlite3
import json
import os
import re
import sys
import random
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge_base import (
    get_year_data, get_events_for_month, get_life_scenes_for_year,
    get_season_scene, get_prices_for_year, get_rmrb_for_date, get_rmrb_for_month
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "timedial.db")
OUTPUT_SCRIPTS = os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json")

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

def _int_to_chinese(n):
    """将0-999的整数转为中文读法，用于金额。例：150→一百五十, 108→一百零八, 45→四十五, 3→三"""
    if n < 0:
        return str(n)
    if n <= 10:
        return CHINESE_NUMS.get(n, str(n))
    if n < 20:
        return "十" + (CHINESE_NUMS[n - 10] if n > 10 else "")
    if n < 100:
        tens, ones = divmod(n, 10)
        return CHINESE_NUMS[tens] + "十" + (CHINESE_NUMS[ones] if ones else "")
    if n < 1000:
        hundreds, rem = divmod(n, 100)
        tens, ones = divmod(rem, 10)
        result = CHINESE_NUMS[hundreds] + "百"
        if rem == 0:
            return result
        if tens == 0:
            return result + "零" + CHINESE_NUMS[ones]
        if ones == 0:
            return result + CHINESE_NUMS[tens] + "十"
        return result + CHINESE_NUMS[tens] + "十" + CHINESE_NUMS[ones]
    return str(n)

def _decimal_to_yuanjiaofen(num_str):
    """将单个小数/整数价格字符串转为'元角分'中文读法。
    例：0.02→二分, 0.1→一角, 0.13→一角三分, 0.56→五角六分,
        1.5→一元五角, 3→三元, 0.08→八分, 0.149→一角五分(四舍五入到分), 150→一百五十元
    """
    try:
        val = float(num_str)
    except (ValueError, TypeError):
        return num_str
    fen_total = round(val * 100)
    if fen_total <= 0:
        return num_str

    yuan = fen_total // 100
    jiao = (fen_total % 100) // 10
    fen = fen_total % 10

    parts = []
    if yuan > 0:
        parts.append(_int_to_chinese(yuan))
        parts.append("元")
    if jiao > 0:
        parts.append(CHINESE_NUMS[jiao])
        parts.append("角")
    if fen > 0:
        parts.append(CHINESE_NUMS[fen])
        parts.append("分")
    return "".join(parts)

def convert_all_decimal_prices(text):
    """将文本中所有形如 X.XX元 / X.X元 / X元 的价格统一转换为元角分中文读法。
    处理范围：
      - '0.02元' → '二分'
      - '大约0.08元' → '大约八分'
      - '0.149元' → '约一角五分'（精度超过分时加'约'）
      - '0.14到0.20元' → '一角四分到二角'
      - '0.03一碗' → '三分一碗'（无元字但直接跟量词）
      - 整数元（如3元、45元、150元）保持汉字数字不变
    注意：统计数字（如21.4万、3.23亿、6.02亿）因后面跟'万/亿'不会被误转换。
    """
    def _replace_price(m):
        prefix = m.group(1) or ""
        num_part = m.group(2)
        if "到" in num_part:
            lo_str, hi_str = [s.strip() for s in num_part.split("到", 1)]
            lo_cn = _decimal_to_yuanjiaofen(lo_str)
            hi_cn = _decimal_to_yuanjiaofen(hi_str)
            return f"{prefix}{lo_cn}到{hi_cn}"
        cn = _decimal_to_yuanjiaofen(num_part)
        try:
            orig = float(num_part)
            fen_approx = abs(orig * 100 - round(orig * 100)) > 0.01
            if fen_approx and "约" not in prefix:
                return f"{prefix}约{cn}"
        except ValueError:
            pass
        return f"{prefix}{cn}"

    def _replace_price_with_unit(m):
        prefix = m.group(1) or ""
        num_part = m.group(2)
        unit = m.group(3)
        if "到" in num_part:
            lo_str, hi_str = [s.strip() for s in num_part.split("到", 1)]
            lo_cn = _decimal_to_yuanjiaofen(lo_str)
            hi_cn = _decimal_to_yuanjiaofen(hi_str)
            return f"{prefix}{lo_cn}到{hi_cn}{unit}"
        cn = _decimal_to_yuanjiaofen(num_part)
        try:
            orig = float(num_part)
            fen_approx = abs(orig * 100 - round(orig * 100)) > 0.01
            if fen_approx and "约" not in prefix:
                return f"{prefix}约{cn}{unit}"
        except ValueError:
            pass
        return f"{prefix}{cn}{unit}"

    text = re.sub(
        r'(大约|约)?\s*([\d]+(?:\.\d+)?(?:\s*到\s*[\d]+(?:\.\d+)?)?)\s*(元)',
        _replace_price,
        text
    )
    text = re.sub(
        r'(大约|约)?\s*([\d]+(?:\.\d+)?(?:\s*到\s*[\d]+(?:\.\d+)?)?)\s*(一碗|一根|一尺|一盒|一支|一块|一袋|一个|一瓶|一条)',
        _replace_price_with_unit,
        text
    )
    return text

def remove_consecutive_duplicate_sentences(text):
    """移除连续重复的句子，以及全文中完全相同的重复句子"""
    sentences = re.split(r'(?<=[。！？])', text)
    result = []
    seen = set()
    prev = None
    for sent in sentences:
        sent_stripped = sent.strip()
        if not sent_stripped:
            result.append(sent)
            continue
        sent_key = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', sent_stripped)
        if sent_stripped == prev:
            continue
        if sent_key and sent_key in seen:
            continue
        if sent_stripped:
            result.append(sent)
            prev = sent_stripped
            if sent_key:
                seen.add(sent_key)
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
        return f"{item_display}"

    if unit:
        return f"{item_display}大约{price_val}{unit}"
    else:
        return f"{item_display}大约{price_val}"

MAJOR_EVENT_CLICHES = [
    "全国人民欢欣鼓舞，大家奔走相告。",
    "全国各族人民无不欢欣鼓舞。",
    "全国各地人民欢欣鼓舞，各界群众纷纷集会庆祝。",
    "广大人民群众无不欢欣鼓舞。",
]

SHORT_NATURAL_ENDINGS = [
    "工人们表示要再接再励。",
    "今年的生产任务有盼头了。",
    "大伙儿听了都很高兴。",
    "当地群众反响热烈。",
    "同志们都很受鼓舞。",
    "村里头都在议论这事。",
    "街坊四邻都听说了。",
    "人们脸上露出了笑容。",
]

CONSTRUCTION_ENDINGS = [
    "工人们纷纷表示要保质保量完成任务。",
    "施工现场一片繁忙景象。",
    "工程技术人员日夜奋战在工地上。",
    "当地群众自发到工地慰问建设者。",
    "厂里的老师傅们都竖起了大拇指。",
    "年轻工人们干活更起劲了。",
    "工地宣传栏里贴满了决心书。",
    "附近的乡亲们都赶来帮忙。",
]

SOCIAL_ENDINGS = [
    "老百姓的日子安稳了许多。",
    "集市上比以前热闹了不少。",
    "供销社里的货物也多了起来。",
    "街道上的宣传栏换了新内容。",
]

SUBSTANTIAL_SUPPLEMENTS = [
    "据了解，这项工作是从年初开始部署的。",
    "有关部门已经发出通知，要求各地认真贯彻执行。",
    "各地正在积极落实相关措施。",
    "这是今年以来取得的又一项重要进展。",
    "负责同志表示，下一步将继续推进各项工作。",
    "当地已经组织群众学习了相关文件精神。",
    "工人们还开展了劳动竞赛，你追我赶搞生产。",
    "附近工厂的工人也前来观摩学习。",
    "不少单位还召开了动员大会，职工们纷纷表态。",
    "据初步统计，各项指标都比去年同期有所提高。",
    "学校里组织学生们上街宣传。",
    "街道居委会也积极配合开展工作。",
    "青年团和妇联组织了各种活动来配合宣传。",
    "消息传开，人们奔走相告。",
    "报纸上也用了很大篇幅来报道。",
    "县城里的黑板报当天就更新了内容。",
    "乡亲们在田间休息时也在议论这事。",
    "区里还专门组织了宣讲队到各单位传达。",
    "工人们下了班也不肯休息，主动加班加点。",
    "当地群众敲锣打鼓到相关单位报喜。",
]

VARIED_ENDINGS = SUBSTANTIAL_SUPPLEMENTS + CONSTRUCTION_ENDINGS[:4] + SOCIAL_ENDINGS[:3] + SHORT_NATURAL_ENDINGS[:3]

EMOTION_CLICHE_WORDS = [
    "欢欣鼓舞", "奔走相告", "干劲十足", "干劲冲天", "无比振奋",
    "喜气洋洋", "一片欢腾", "意气风发", "热情更加高涨", "由衷的高兴",
    "心情格外激动", "干劲更足",
]

MONTH_NAMES = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月"
}

HARD_NEWS_OPENINGS = [
    "新华社消息，",
    "本台消息，",
    "中央人民广播电台消息，",
    "最新消息，",
    "据人民日报报道，",
    "中央台记者报道，",
    "记者从有关方面获悉，",
    "今天的消息说，",
    "大家注意了，",
    "各位听众请注意，",
]

GOOD_NEWS_OPENINGS = [
    "好消息！",
    "同志们，报告大家一个好消息！",
    "告诉大家一个好消息，",
    "特大喜讯！",
]

WAR_OPENINGS = [
    "来自前线的消息，",
    "前线最新消息，",
]

SOFT_NEWS_OPENINGS = [
    "各位听众同志们，",
    "各位听众朋友们，",
    "乡亲们，同志们，",
    "各位老乡，",
    "同志们，",
    "听众朋友们，",
    "各位乡亲，",
]

ALL_OPENINGS = HARD_NEWS_OPENINGS + GOOD_NEWS_OPENINGS + WAR_OPENINGS + SOFT_NEWS_OPENINGS

TRANSITIONS = [
    "另外，",
    "再来看一条消息，",
    "说到这里，",
    "与此同时，",
    "还有一条消息，",
]

FOREIGN_KEYWORDS = {
    "B-50", "超级堡垒", "环球飞行", "欧洲经济共同体", "共同市场",
    "北约", "华约", "马歇尔计划", "喀麦隆", "托管区", "殖民地",
    "法国托管区", "英国托管区", "宣布独立",
}

FOREIGN_COUNTRY_NAMES = {
    "美国", "英国", "法国", "德国", "日本", "欧洲", "苏联", "印度",
    "巴基斯坦", "尼泊尔", "蒙古", "阿富汗", "缅甸", "印尼", "印度尼西亚",
}

CHINA_RELATED_DIPLOMACY = {
    "中缅", "中尼", "中蒙", "中巴", "中阿", "中美", "中苏", "中英", "中法", "中日",
    "中国和", "我国与", "边界", "协定", "条约", "友好", "外交", "访问",
    "周恩来", "总理", "主席",
}

HINDSIGHT_WORDS = {"那时候", "当时", "后来", "众所周知", "遗憾的是"}

DATE_FULL_DAYS = [1, 10, 20]

TERMS_TO_RESTORE = {
    "仅限官方定性表述": "反革命",
}

MANUAL_EVENTS = {
    (1949, 10): "中央人民广播电台！各位听众同志们，今天是一九四九年十月一日，中华人民共和国中央人民政府今天成立了！中国人民从此站起来了！毛泽东主席在天安门城楼上庄严宣告，中华人民共和国中央人民政府成立了。",
    (1950, 6):  "新华社消息，朝鲜战争爆发。美国总统杜鲁门宣布武装干涉朝鲜内政，同时派遣第七舰队侵入台湾海峡。全国各地人民纷纷集会，坚决反对美帝国主义的侵略行径。",
    (1950, 10): "同志们！最新消息：中国人民志愿军已于十月二十五日跨过鸭绿江，奔赴朝鲜前线，抗美援朝，保家卫国！雄赳赳，气昂昂，跨过鸭绿江，保和平，卫祖国，就是保家乡。",
    (1951, 5):  "新华社消息，中央人民政府和西藏地方政府在北京签订《关于和平解放西藏办法的协议》，西藏宣告和平解放。祖国大陆实现了完全统一，各族人民团结在毛主席的旗帜下。",
    (1951, 12): "各位听众，中共中央作出决定，在全国党政机关工作人员中开展反贪污、反浪费、反官僚主义的三反运动，坚决打击资产阶级的猖狂进攻。",
    (1952, 1):  "同志们，继三反运动之后，中共中央又决定在全国资本主义工商业者中开展反行贿、反偷税漏税、反盗骗国家财产、反偷工减料、反盗窃国家经济情报的五反运动。",
    (1952, 7):  "好消息！新中国第一条铁路干线成渝铁路全线通车啦！全长五百零五公里，从成都到重庆，四川人民四十年的愿望终于实现了！",
    (1952, 10): "来自前线的消息，上甘岭战役正在激烈进行中。我志愿军指战员在极其艰苦的条件下，依托坑道工事，打退了敌人无数次进攻，涌现出黄继光、孙占元等战斗英雄。",
    (1953, 7):  "同志们！特大喜讯！朝鲜停战协定已于七月二十七日在板门店签字，历时三年的朝鲜战争胜利结束！中朝两国人民和军队打败了美帝国主义，保卫了远东和世界和平！",
    (1953, 10): "第一个五年计划开始实施！全国人民正在为实现社会主义工业化而努力奋斗。一百五十六个重点工程正在加紧建设，新中国的工业面貌即将焕然一新。",
    (1953, 12): "周恩来总理在接见印度代表团时，首次提出和平共处五项原则：互相尊重主权和领土完整、互不侵犯、互不干涉内政、平等互利、和平共处。",
    (1954, 4):  "日内瓦会议召开，周恩来总理率代表团出席。这是新中国首次以五大国之一的身份参加国际会议，讨论和平解决朝鲜问题和恢复印度支那和平问题。",
    (1954, 9):  "第一届全国人民代表大会第一次会议在北京隆重举行，大会通过了《中华人民共和国宪法》，这是新中国第一部社会主义类型的宪法。毛泽东同志当选为中华人民共和国主席。",
    (1954, 12): "康藏公路和青藏公路同时全线通车！两路全长四千三百多公里，结束了西藏没有公路的历史，加强了西藏与内地的联系，巩固了祖国西南边防。",
    (1955, 4):  "周恩来总理率领中国代表团出席在印度尼西亚万隆召开的亚非会议，提出求同存异的方针，推动会议取得圆满成功。和平共处五项原则走向世界。",
    (1955, 9):  "中华人民共和国主席授衔授勋典礼在北京隆重举行。朱德、彭德怀、林彪、刘伯承、贺龙、陈毅、罗荣桓、徐向前、聂荣臻、叶剑英被授予中华人民共和国元帅军衔。",
    (1955, 10): "新疆维吾尔自治区正式成立，赛福鼎同志当选为自治区人民委员会主席。这是新中国民族区域自治政策的伟大胜利，各族人民欢欣鼓舞。",
    (1956, 7):  "同志们！第一汽车制造厂在长春建成并试制成功第一批解放牌载重汽车！中国制造不出汽车的历史从此结束了！全厂职工欢呼雀跃，敲锣打鼓向毛主席报喜！",
    (1956, 9):  "中国共产党第八次全国代表大会在北京召开。大会指出，国内的主要矛盾已经是人民对于经济文化迅速发展的需要同当前经济文化不能满足人民需要的状况之间的矛盾。",
    (1957, 2):  "新华社消息，毛主席发表《关于正确处理人民内部矛盾的问题》的重要讲话，提出了正确区分和处理社会主义社会中敌我矛盾和人民内部矛盾的学说。",
    (1957, 10): "长江大桥通车啦！武汉长江大桥正式建成通车，一桥飞架南北，天堑变通途！这是万里长江上的第一座大桥，全长一千六百七十米，连接京汉和粤汉铁路。",
    (1958, 5):  "同志们！中共八大二次会议在北京召开，正式通过了鼓足干劲、力争上游、多快好省地建设社会主义的总路线。全国人民意气风发，掀起了大跃进的高潮。",
    (1958, 8):  "最新消息！中共中央政治局扩大会议在北戴河举行，通过了在农村建立人民公社的决议。全民大炼钢铁运动在全国展开，男女老少齐上阵，小高炉遍地开花。",
    (1958, 9):  "好消息！北京电视台正式开播，这是中国第一座电视台，中国的电视事业从此诞生了！全国各地人民开始能够看到电视节目了。",
    (1959, 3):  "新华社消息，西藏地方政府和上层反动集团发动武装叛乱，人民解放军驻藏部队奉命进行平叛作战，维护国家统一和民族团结。",
    (1959, 4):  "特大喜讯！容国团同志在第二十五届世界乒乓球锦标赛上荣获男子单打冠军，这是中国运动员第一次在世界锦标赛中获得世界冠军称号，全国人民欢欣鼓舞！",
    (1959, 9):  "第一届全国运动会在北京工人体育场隆重开幕！毛泽东、刘少奇、周恩来、朱德等党和国家领导人出席开幕式。这是新中国成立以来规模最大的一次体育盛会。",
    (1959, 10): "今天，首都北京隆重举行中华人民共和国成立十周年庆祝大会，毛泽东主席和党和国家领导人出席。建国十年，祖国面貌焕然一新，社会主义建设取得辉煌成就。",
    (1959, 11): "好消息！第一拖拉机制造厂在河南洛阳建成投产，新中国开始自己制造拖拉机了！东方红拖拉机开上了农业生产第一线，农业机械化迈出了重要一步。",
    (1960, 2):  "特大喜讯！大庆石油会战开始了！石油工业部集中全国力量在大庆地区开展石油勘探开发大会战，决心甩掉中国贫油的帽子。铁人王进喜同志带领钻井队日夜奋战在工地上，工人们喊出了'宁可少活二十年，拼命也要拿下大油田'的口号。",
    (1960, 5):  "同志们！中国登山队队员王富洲、贡布、屈银华于五月二十五日凌晨从北坡成功登上世界最高峰珠穆朗玛峰！人类第一次战胜珠峰北坡天险，为祖国争了光！",
    (1960, 11): "中共中央发出关于农村人民公社当前政策问题的紧急指示信，要求坚决纠正一平二调的共产风，认真执行按劳分配原则，调动广大农民的生产积极性。",
}

EARLY_50S_SCENES = {"互助组", "合作社", "土地改革", "三反五反", "抗美援朝"}
LATE_50S_SCENES = {"人民公社", "大跃进", "大炼钢铁", "公共食堂"}
SCENES_1963_PLUS = {"雷锋", "向雷锋同志学习", "做好事"}
SCENES_1964_PLUS = {"工业学大庆", "农业学大寨", "陈永贵", "学大寨"}
SCENES_TO_AVOID_1960 = {
    "串联", "红袖章", "绿军装", "红卫兵", "文革", "样板戏", "红灯记", "沙家浜",
    "智取威虎山", "革命现代京剧", "李铁梅", "杨子荣", "阿庆嫂", "上山下乡", "知青",
    "广阔天地", "语录歌", "忠字舞", "表忠心", "早请示晚汇报", "跳忠字舞",
    "万寿无疆", "永远健康", "最高指示",
}


def scene_appropriate_for_year(scene_name, scene_text, year):
    combined = scene_name + scene_text
    if any(kw in combined for kw in SCENES_TO_AVOID_1960) and year <= 1970:
        return False
    if year < 1958 and any(kw in combined for kw in LATE_50S_SCENES):
        return False
    if year < 1963 and any(kw in combined for kw in SCENES_1963_PLUS):
        return False
    if year < 1964 and any(kw in combined for kw in SCENES_1964_PLUS):
        return False
    return True


def select_appropriate_life_scene(life_scenes, year, month):
    appropriate = []
    for scene in life_scenes:
        name = scene.get('name', '')
        scene_text = scene.get('scene', '')
        if scene_appropriate_for_year(name, scene_text, year):
            appropriate.append(scene)
    return appropriate


def is_china_relevant(title):
    if not title:
        return False
    if any(kw in title for kw in FOREIGN_KEYWORDS):
        return False
    china_keywords = {"中国", "中华人民共和国", "北京", "毛主席", "党中央", "全国", "我国", "我", "人民", "解放军", "志愿军", "新中国"}
    if any(kw in title for kw in china_keywords):
        return True
    if any(kw in title for kw in CHINA_RELATED_DIPLOMACY):
        return True
    if any(kw in title for kw in {"抗美援朝", "鸭绿江", "板门店", "上甘岭", "朝鲜"}):
        return True
    if "苏联" in title and any(kw in title for kw in {"援助", "专家", "友好", "签订"}):
        return True
    if any(kw in title for kw in {"铁路", "公路", "大桥", "工厂", "水库", "水利", "油田"}):
        return True
    return False


def remove_future_year_sentences(text, current_year, current_month=None):
    sentences = re.split(r'(?<=[。！？])', text)
    kept = []
    hindsight_keywords = {"此后", "后来", "至今", "为以后", "为今后", "陆续与", "又陆续", "为后来", "到...年", "到...底"}
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


def simple_clean_text(text, year):
    if not text:
        return ""
    result = text
    result = result.replace("——", "")
    result = re.sub(r"[~～]+", "", result)
    result = re.sub(r"\[\d+[-\-－]\d+\]", "", result)
    result = re.sub(r"广播里说[，,]", "同志们，", result)
    result = re.sub(r"广播里反复播报着这个消息[。！]", "消息传开，人们奔走相告。", result)
    result = re.sub(r"广播里", "本台", result)
    for word in HINDSIGHT_WORDS:
        result = result.replace(word, "")
    for wrong, correct in TERMS_TO_RESTORE.items():
        result = result.replace(wrong, correct)
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
        result = result.replace("社员们", "农民们")
        result = result.replace("社员同志", "乡亲们")
        result = result.replace("社员", "农民")
    result = re.sub(r"\d{1,2}月\d{1,2}日[——\-—\s]*", "", result)
    result = re.sub(r"^[\s，,。！？]+", "", result)
    result = re.sub(r'([。！？])\1+', r'\1', result)
    result = re.sub(r'[，,]{2,}', '，', result)
    result = re.sub(r'\s+', ' ', result)
    result = result.strip()
    if result and result[-1] not in "。！？":
        result = result + "。"
    return result


def fix_missing_punctuation(text):
    """修复句子间缺少标点的问题，如'纪录这是' -> '纪录。这是'"""
    if not text:
        return text
    result = text
    insert_positions = []
    specific_patterns = [
        ('纪录', '这是'), ('成功', '这'), ('胜利', '这'),
        ('结束了', '这'), ('完成了', '这'), ('实现了', '这'),
        ('诞生了', '这'), ('成立了', '这'), ('通车了', '这'),
    ]
    for before, after in specific_patterns:
        idx = 0
        while True:
            pos = result.find(before + after, idx)
            if pos == -1:
                break
            insert_pos = pos + len(before)
            insert_positions.append(insert_pos)
            idx = pos + len(before)
    transition_words = ['另外，', '再来看一条消息，', '说到这里，', '与此同时，', '还有一条消息，']
    for trans in transition_words:
        idx = 0
        while True:
            pos = result.find(trans, idx)
            if pos == -1:
                break
            if pos > 0 and result[pos-1] not in '。！？；：\n':
                insert_positions.append(pos)
            idx = pos + len(trans)
    insert_positions = sorted(set(insert_positions), reverse=True)
    for pos in insert_positions:
        result = result[:pos] + '。' + result[pos:]
    return result

def is_substantial_sentence(sentence):
    """判断句子是否有实质内容（不是纯情绪词堆砌）"""
    if not sentence:
        return False
    clean_s = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', sentence)
    if len(clean_s) < 4:
        return False
    emotion_only_patterns = [
        '欢欣鼓舞扬眉吐气',
        '为建设新中国而努力奋斗',
        '干劲十足建设热情更加高涨',
    ]
    for pat in emotion_only_patterns:
        if pat in sentence and len(clean_s) < 20:
            return False
    return True


def is_hollow_ending(sentence):
    """判断句子是否为纯空洞套话结尾（无具体名词、事件、数据）"""
    if not sentence:
        return False
    clean_s = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', sentence)
    if len(clean_s) < 4:
        return True
    hollow_indicators = [
        "欢欣鼓舞", "奔走相告", "干劲十足", "干劲冲天", "无比振奋",
        "喜气洋洋", "一片欢腾", "意气风发", "热情更加高涨", "由衷的高兴",
        "心情格外激动", "干劲更足", "建设热情", "更大干劲", "欢腾",
        "为建设新中国而努力奋斗", "为建设国家出力", "贡献自己的力量",
        "到处都是喜气洋洋", "心情无比激动",
    ]
    substance_words = [
        "工厂", "农村", "铁路", "公路", "大桥", "水库", "工地", "车间",
        "田", "地", "公社", "合作社", "互助组", "学校", "商店", "供销社",
        "工人", "农民", "社员", "同志", "师傅", "学生", "群众", "居民",
        "北京", "上海", "天津", "重庆", "省", "市", "县", "区", "乡", "村",
        "吨", "斤", "尺", "亩", "里", "公里", "米", "元", "角", "分",
        "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "万",
        "计划", "任务", "生产", "产量", "指标", "质量", "安全",
        "今年", "本月", "当天", "昨日", "今天",
        "会议", "决定", "通知", "文件", "指示", "报告",
        "通车", "投产", "建成", "完工", "开工", "试制", "竣工",
    ]
    hollow_word_count = sum(1 for w in hollow_indicators if w in sentence)
    substance_word_count = sum(1 for w in substance_words if w in sentence)
    has_number = bool(re.search(r'\d', clean_s))
    if hollow_word_count >= 1 and substance_word_count == 0 and not has_number:
        if len(clean_s) <= 25:
            return True
    if hollow_word_count >= 2 and substance_word_count <= 1 and len(clean_s) <= 20:
        return True
    all_cliche_sentences = {
        "人们的心情格外激动", "大家纷纷表示要以更大干劲投入建设",
        "工厂农村一片欢腾", "同志们的干劲更足了",
        "建设祖国的热情更加高涨", "全国人民欢欣鼓舞大家奔走相告",
        "全国各族人民无不欢欣鼓舞", "全国各地人民欢欣鼓舞各界群众纷纷集会庆祝",
        "大家干劲十足建设热情更加高涨", "广大人民群众无不欢欣鼓舞",
        "消息传来人们都感到无比振奋", "这一喜讯让大家都感到由衷的高兴",
        "工厂里农村里到处都是喜气洋洋的景象",
        "人们干劲十足地建设祖国", "家家户户都在为建设国家出力",
        "全国人民干劲十足", "大家你追我赶争取为国家多做贡献",
        "建设我们的新中国", "建设我们伟大的祖国",
    }
    if clean_s in all_cliche_sentences:
        return True
    return False


def deduplicate_emotion_words(text):
    """同一篇text中相同情绪词最多出现1次，移除后续重复"""
    sentences = re.split(r'(?<=[。！？])', text)
    found_emotions = set()
    result_parts = []
    for s in sentences:
        s_stripped = s.strip()
        if not s_stripped:
            result_parts.append(s)
            continue
        modified = s
        for word in EMOTION_CLICHE_WORDS:
            if word in found_emotions and word in modified:
                modified = modified.replace(word, "")
            elif word in modified:
                count = modified.count(word)
                if count > 1:
                    first_idx = modified.find(word)
                    modified = modified[:first_idx + len(word)] + modified[first_idx + len(word):].replace(word, "")
                found_emotions.add(word)
        modified = re.sub(r'[，,、]{2,}', '，', modified)
        modified = re.sub(r'^[，,、；;：:]+', '', modified)
        result_parts.append(modified)
    result = "".join(result_parts)
    result = re.sub(r'。[，,、]+', '。', result)
    result = re.sub(r'[，,、]+。', '。', result)
    result = re.sub(r'([，,、])\1+', r'\1', result)
    return result


def clean_hollow_endings(text, is_major_event=False):
    """检查新闻结尾，如果最后一句是纯空洞套话则删除（重大事件除外）"""
    if is_major_event:
        return text
    sentences = re.split(r'(?<=[。！？])', text)
    sentences = [s for s in sentences if s.strip()]
    while len(sentences) > 1:
        last = sentences[-1].strip()
        if is_hollow_ending(last):
            sentences.pop()
        else:
            break
    result = "".join(sentences)
    result = re.sub(r'[，,、；;：:\s]+$', '', result)
    if result and result[-1] not in "。！？":
        result = result + "。"
    return result


def post_process_news_text(text, is_manual_event=False):
    """新闻文本最终后处理：去重情绪词 + 清理空洞结尾"""
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=is_manual_event)
    return text


def clean_broadcast_text(text, year, month=None):
    if not text:
        return ""
    text = simple_clean_text(text, year)
    text = fix_missing_punctuation(text)
    text = remove_future_year_sentences(text, year, month)
    text = re.sub(r'([。！？])\1+', r'\1', text)
    text = re.sub(r'[，,]{2,}', '，', text)
    sentences = re.split(r'(?<=[。！？])', text)
    kept = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        has_foreign = False
        for kw in FOREIGN_KEYWORDS:
            if kw in s:
                has_foreign = True
                break
        if has_foreign:
            is_diplomacy = False
            for dip in ["中", "我国", "总理", "主席", "周恩来", "协定", "条约", "边界", "友好"]:
                if dip in s:
                    is_diplomacy = True
                    break
            if not is_diplomacy:
                continue
        if any(kw in s for kw in SCENES_TO_AVOID_1960) and year <= 1970:
            continue
        s = s.strip("，,；;：: ")
        if not s:
            continue
        s_clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', s)
        if len(s_clean) < 4:
            continue
        if s[-1] not in "。！？":
            s = s + "。"
        kept.append(s)
    result = "".join(kept).strip()
    result = re.sub(r'^[，,。！？\s]+', '', result)
    if result and result[-1] not in "。！？":
        result = result + "。"
    return result


def get_db_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT date, year, month, day, title, summary, importance
        FROM historical_events
        WHERE year >= 1949 AND year <= 1960
        ORDER BY importance DESC, date ASC
    """)
    rows = cur.fetchall()
    conn.close()
    monthly = {}
    seen_titles = set()
    for r in rows:
        try:
            y = r['year']
            m = r['month']
            if not (1949 <= y <= 1960 and 1 <= m <= 12):
                continue
            key = (y, m)
            title = (r['title'] or '').strip()
            if len(title) < 20:
                continue
            if not is_china_relevant(title):
                continue
            if title in seen_titles:
                continue
            seen_titles.add(title)
            if key not in monthly:
                monthly[key] = []
            monthly[key].append(dict(r))
        except Exception:
            pass
    return monthly


def categorize_event(title, text):
    war_keywords = {"战役", "战", "军", "志愿军", "前线", "战场", "抗美援朝", "敌", "战斗", "入侵", "平叛", "叛乱"}
    construction_keywords = {"建成", "通车", "投产", "试制", "开工", "落成", "厂", "铁路", "公路", "大桥", "水利", "截流", "电视台", "开播"}
    policy_keywords = {"会议", "决定", "决议", "宪法", "政策", "指示", "法令", "协定", "条约", "成立", "选举"}
    if any(kw in title or kw in text for kw in war_keywords):
        return "war"
    if any(kw in title or kw in text for kw in construction_keywords):
        return "construction"
    if any(kw in title or kw in text for kw in policy_keywords):
        return "hard"
    if any(kw in title or kw in text for kw in {"物价", "生活", "供应", "粮", "布", "老百姓", "日子"}):
        return "life"
    return "hard"


def is_similar_title(t1, t2):
    if not t1 or not t2:
        return False
    t1_clean = re.sub(r'[^\u4e00-\u9fa5]', '', t1)
    t2_clean = re.sub(r'[^\u4e00-\u9fa5]', '', t2)
    if not t1_clean or not t2_clean:
        return False
    if len(t1_clean) < 4 or len(t2_clean) < 4:
        return False
    for i in range(len(t1_clean) - 3):
        sub4 = t1_clean[i:i+4]
        if sub4 in t2_clean:
            return True
    return False


def generate_event_broadcast(evt, opening, year, month):
    day = evt.get('day')
    title = (evt.get('title') or '').strip()
    title = remove_future_year_sentences(title, year, month)
    detail = (evt.get('detail') or evt.get('summary') or '').strip()
    day_str = f"{day}日" if day else ""
    rng_local = random.Random(f"{year}_{month}_{title[:10]}")
    title_clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', title)
    if detail:
        detail = remove_future_year_sentences(detail, year, month)
        detail_short = detail
        if len(detail_short) > 100:
            cut_pos = detail_short.rfind("。", 0, 100)
            if cut_pos >= 30:
                detail_short = detail_short[:cut_pos + 1]
            else:
                detail_short = detail_short[:100]
        detail_clean = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', detail_short)
        if title_clean and detail_clean and (title_clean in detail_clean or detail_clean in title_clean or len(set(title_clean) & set(detail_clean)) / max(1, len(set(title_clean))) > 0.8):
            if len(detail_clean) > len(title_clean) * 1.5:
                pass
            else:
                detail_short = ""
    else:
        detail_short = ""
    text = f"{opening}{month}月{day_str}，{title}。{detail_short}"
    temp_for_len = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
    if len(temp_for_len) < 55:
        category = categorize_event(title, title + (detail or ''))
        if category == "construction":
            supplement_pool = SUBSTANTIAL_SUPPLEMENTS + CONSTRUCTION_ENDINGS
        elif category == "life" or category == "soft":
            supplement_pool = SUBSTANTIAL_SUPPLEMENTS + SOCIAL_ENDINGS
        else:
            supplement_pool = SUBSTANTIAL_SUPPLEMENTS
        extra = rng_local.choice(supplement_pool)
        text = f"{opening}{month}月{day_str}，{title}。{detail_short}{extra}"
    text = simple_clean_text(text, year)
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=False)
    return text


def generate_construction_broadcast(title, opening, year, month):
    rng_local = random.Random(f"{year}_{month}_const")
    ending = ""
    if rng_local.random() < 0.5:
        ending = rng_local.choice(CONSTRUCTION_ENDINGS + SHORT_NATURAL_ENDINGS[:4])
    if "好消息" in opening:
        templates = [
            f"{opening}本月，{title}的消息传来。工人们加班加点，争取早日完工。{ending}",
            f"{opening}{month}月里，{title}，这是我国社会主义建设的又一项新进展。{ending}",
            f"{opening}{title}。{ending}",
        ]
    else:
        templates = [
            f"{opening}本月，{title}的消息传来。工人们加班加点，争取早日完工。{ending}",
            f"{opening}{month}月里，{title}，这是我国社会主义建设的又一项新进展。{ending}",
            f"{opening}好消息，{title}。{ending}",
        ]
    text = rng_local.choice(templates)
    text = simple_clean_text(text, year)
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=False)
    return text


def parse_price_string(price_str):
    price_str = price_str.strip()
    price_str = re.sub(r'^约\s*', '', price_str)
    price_str = re.sub(r'^大约\s*', '', price_str)
    unit_match = re.search(r'/斤$', price_str)
    unit = "一斤" if unit_match else ""
    price_value = re.sub(r'/斤$', '', price_str).strip()
    return price_value, unit


def generate_life_broadcast(prices, life_scenes, year_data, opening, year, month):
    rng_local = random.Random(f"{year}_{month}_life")
    is_hardship_year = 1959 <= year <= 1961
    mood = year_data.get('mood', '')
    key_event = year_data.get('key_event', '')
    appropriate_scenes = select_appropriate_life_scene(life_scenes, year, month)
    parts = []
    price_talk = []
    if prices:
        price_items = list(prices.items())
        rng_local.shuffle(price_items)
        selected_items = price_items[:3]
        for item, price_str in selected_items:
            price_phrase = parse_and_format_price(item, price_str)
            if price_phrase:
                price_talk.append(price_phrase)
        if price_talk:
            parts.append("说到物价，" + "，".join(price_talk))
    if appropriate_scenes:
        scene = rng_local.choice(appropriate_scenes)
        scene_text = scene.get('scene', '')
        if scene_text:
            parts.append(scene_text)
    if not parts and mood:
        parts.append(mood)
    if not parts and key_event:
        parts.append(key_event)
    if not parts:
        parts.append("老百姓的日子安稳，大家积极生产")
    detail = "，".join(parts)
    if is_hardship_year:
        ending = "全国人民正在党中央领导下，团结一致，艰苦奋斗，克服眼前的暂时困难。"
    else:
        ending = "老百姓的日子越过越有奔头。"
    text = f"{opening}说到眼下的生活，{detail}，{ending}"
    text = simple_clean_text(text, year)
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=False)
    return text


def generate_season_broadcast(season_scene, opening, year, month):
    month_season_map = {
        3: ("初春", "春暖花开"), 4: ("春天", "春光明媚"), 5: ("暮春", "春意盎然"),
        6: ("初夏", "万物蓬勃"), 7: ("盛夏", "骄阳似火"), 8: ("夏末", "暑气渐消"),
        9: ("初秋", "秋高气爽"), 10: ("金秋", "硕果累累"), 11: ("深秋", "秋风送爽"),
        12: ("隆冬", "天寒地冻"), 1: ("寒冬", "北风凛冽"), 2: ("残冬", "冬去春来"),
    }
    season_name, season_adj = month_season_map.get(month, ("时节", "美好"))
    farmer_word = "社员们" if year >= 1958 else "农民们"
    activities = [
        "工人们在车间里加紧生产",
        f"{farmer_word}在田地里辛勤劳作",
        "街道上人们来来往往，各忙各的",
        "学校里孩子们正在认真读书",
        "供销社里人来人往，很是热闹",
    ]
    rng_local = random.Random(f"{year}_{month}_season")
    activity = rng_local.choice(activities)
    text = f"{opening}眼下正是{season_name}，{season_scene}。在这{season_adj}的日子里，{activity}。"
    text = simple_clean_text(text, year)
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=False)
    return text


def effective_length(text):
    """计算有效中文字符+数字字母长度"""
    return len(re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text))


def is_foreign_event(text):
    """检查是否为外国事件"""
    if any(kw in text for kw in FOREIGN_KEYWORDS):
        return True
    foreign_countries = ["以色列", "英国", "法国", "德国", "日本", "印度", "巴基斯坦", "尼泊尔", "蒙古", "阿富汗", "缅甸", "印尼", "印度尼西亚", "喀麦隆", "殖民地", "托管区"]
    china_related = ["中缅", "中尼", "中蒙", "中巴", "中阿", "中美", "中苏", "中英", "中法", "中日", "中国", "我国", "周恩来", "总理", "主席"]
    if any(fc in text for fc in foreign_countries):
        if not any(cr in text for cr in china_related):
            return True
    foreign_names = ["大卫", "本-古理安", "杜鲁门", "丘吉尔", "阿登纳", "吉田茂"]
    if any(fn in text for fn in foreign_names):
        if not any(cr in text for cr in china_related):
            return True
    return False

def generate_rmrb_broadcast(paragraphs, opening, year, month):
    if not paragraphs:
        return ""
    rng_local = random.Random(f"{year}_{month}_rmrb")
    valid_paras = []
    for p in paragraphs:
        p_stripped = p.strip()
        if p_stripped.startswith("【") and p_stripped.endswith("】"):
            continue
        if len(p_stripped) < 30:
            continue
        if is_foreign_event(p_stripped):
            continue
        if len(p_stripped) > 120:
            cut_pos = p_stripped.rfind("。", 0, 120)
            if cut_pos >= 30:
                p_stripped = p_stripped[:cut_pos + 1]
            else:
                p_stripped = p_stripped[:120] + "。"
        if is_china_relevant(p_stripped) and "人民日报" not in p_stripped[:20]:
            valid_paras.append(p_stripped)
    if not valid_paras:
        for p in paragraphs:
            p_stripped = p.strip()
            if len(p_stripped) >= 20 and is_china_relevant(p_stripped) and not is_foreign_event(p_stripped):
                if len(p_stripped) > 100:
                    cut_pos = p_stripped.rfind("。", 0, 100)
                    if cut_pos >= 20:
                        p_stripped = p_stripped[:cut_pos + 1]
                    else:
                        p_stripped = p_stripped[:100] + "。"
                valid_paras.append(p_stripped)
    if not valid_paras:
        return ""
    num_select = min(1, len(valid_paras))
    selected = rng_local.sample(valid_paras, num_select)
    text = f"{opening}据人民日报报道，{''.join(selected)}"
    text = simple_clean_text(text, year)
    text = deduplicate_emotion_words(text)
    text = clean_hollow_endings(text, is_major_event=False)
    return text


class OpeningPicker:
    def __init__(self, rng):
        self.rng = rng
        self.all_used = set()
        self.used = {
            "hard": set(),
            "construction": set(),
            "war": set(),
            "soft": set(),
        }

    def pick(self, category):
        if category == "war":
            pool = WAR_OPENINGS
            used_set = self.used["war"]
            cross_pool = HARD_NEWS_OPENINGS
        elif category == "construction":
            pool = GOOD_NEWS_OPENINGS
            used_set = self.used["construction"]
            cross_pool = HARD_NEWS_OPENINGS + SOFT_NEWS_OPENINGS
        elif category == "life" or category == "soft":
            pool = SOFT_NEWS_OPENINGS
            used_set = self.used["soft"]
            cross_pool = HARD_NEWS_OPENINGS
        else:
            pool = HARD_NEWS_OPENINGS
            used_set = self.used["hard"]
            cross_pool = SOFT_NEWS_OPENINGS
        available = [o for o in pool if o not in used_set and o not in self.all_used]
        if not available:
            available = [o for o in pool if o not in used_set]
        if not available:
            used_set.clear()
            available = pool[:]
        if self.rng.random() < 0.25:
            cross_available = [o for o in cross_pool if o not in self.all_used]
            if cross_available:
                chosen = self.rng.choice(cross_available)
                self.all_used.add(chosen)
                return chosen
        chosen = self.rng.choice(available)
        used_set.add(chosen)
        self.all_used.add(chosen)
        return chosen


def generate_month_news(year, month, db_events):
    rng = random.Random(f"{year}_{month}")
    news_items = []
    opening_picker = OpeningPicker(rng)

    manual_text = MANUAL_EVENTS.get((year, month))
    if manual_text:
        cleaned_manual = simple_clean_text(manual_text, year)
        if cleaned_manual:
            news_items.append(cleaned_manual)

    kb_events = get_events_for_month(year, month)
    year_data = get_year_data(year)
    prices = get_prices_for_year(year)
    life_scenes = get_life_scenes_for_year(year)
    season_scene = get_season_scene(month, year=year)

    rmrb_content = []
    for day in DATE_FULL_DAYS:
        rmrb_paras = get_rmrb_for_date(year, month, day)
        if rmrb_paras:
            rmrb_content.extend([p for p in rmrb_paras if len(p) > 20])
    if not rmrb_content:
        rmrb_month_paras = get_rmrb_for_month(year, month)
        rmrb_content.extend([p for p in rmrb_month_paras if len(p) > 20])

    db_month_events = db_events.get((year, month), [])

    def is_too_similar(new_text):
        new_clean = re.sub(r'[^\u4e00-\u9fa5]', '', new_text)
        for existing in news_items:
            existing_clean = re.sub(r'[^\u4e00-\u9fa5]', '', existing)
            if is_similar_title(new_clean, existing_clean):
                return True
        return False

    event_candidates = []
    for evt in kb_events:
        title = (evt.get('title') or '').strip()
        if not title:
            continue
        if is_too_similar(title):
            continue
        event_candidates.append(("kb", evt))
    for evt in db_month_events[:10]:
        title = (evt.get('title') or '').strip()
        if not title:
            continue
        if is_too_similar(title):
            continue
        event_candidates.append(("db", {"title": title, "day": evt.get('day'), "detail": evt.get('summary', '')}))

    target_count = rng.randint(6, 8)
    if rmrb_content:
        target_count = max(target_count, 7)

    BAD_CONTENT_KEYWORDS = [
        "蒋介石", "国民党迁至", "迁至台北",
        "大火", "火灾", "无家可归",
        "三一事件", "以色列", "大卫·本-古理安",
        "当选以色列", "越南人民", "奠边府",
        "朝鲜战争：",
    ]
    def is_appropriate(text):
        for kw in BAD_CONTENT_KEYWORDS:
            if kw in text:
                return False
        if is_foreign_event(text):
            return False
        return True
    def add_if_ok(text):
        if text and is_appropriate(text) and not is_too_similar(text):
            news_items.append(text)
            return True
        return False

    if not manual_text and event_candidates:
        source, evt = event_candidates.pop(0)
        title = evt.get('title', '')
        category = categorize_event(title, title + (evt.get('detail') or ''))
        op = opening_picker.pick(category)
        if category == "construction" and not evt.get('detail'):
            text = generate_construction_broadcast(title, op, year, month)
        else:
            text = generate_event_broadcast(evt, op, year, month)
        add_if_ok(text)

    rmrb_added = False
    if rmrb_content:
        op = opening_picker.pick("hard")
        text = generate_rmrb_broadcast(rmrb_content, op, year, month)
        if add_if_ok(text):
            rmrb_added = True

    max_events_before_other = 6 if manual_text else 5
    while len(news_items) < max_events_before_other and event_candidates:
        source, evt = event_candidates.pop(0)
        title = evt.get('title', '')
        category = categorize_event(title, title + (evt.get('detail') or ''))
        op = opening_picker.pick(category)
        if category == "construction" and not evt.get('detail'):
            text = generate_construction_broadcast(title, op, year, month)
        else:
            text = generate_event_broadcast(evt, op, year, month)
        add_if_ok(text)

    if len(news_items) < target_count and (prices or life_scenes):
        op = opening_picker.pick("life")
        text = generate_life_broadcast(prices, life_scenes, year_data, op, year, month)
        add_if_ok(text)

    while len(news_items) < target_count and event_candidates:
        source, evt = event_candidates.pop(0)
        title = evt.get('title', '')
        category = categorize_event(title, title + (evt.get('detail') or ''))
        op = opening_picker.pick(category)
        if category == "construction" and not evt.get('detail'):
            text = generate_construction_broadcast(title, op, year, month)
        else:
            text = generate_event_broadcast(evt, op, year, month)
        add_if_ok(text)

    if len(news_items) < target_count and season_scene:
        season_cat = "hard" if rng.random() < 0.4 else "soft"
        op = opening_picker.pick(season_cat)
        text = generate_season_broadcast(season_scene, op, year, month)
        add_if_ok(text)

    def make_phrase_from_keywords(kw_text):
        if not kw_text:
            return "推进各项建设工作"
        if "、" in kw_text or "，" in kw_text or len(kw_text) < 10:
            return f"推进{year_data.get('title', '新中国建设')}的各项工作"
        return kw_text
    
    fallback_index = 0
    while len(news_items) < 6:
        key_evt = make_phrase_from_keywords(year_data.get('key_event', ''))
        fallback_texts = [
            f"全国各地正在{key_evt}，工厂里工人们加班加点生产，农村里农民们辛勤耕作，各条战线都在积极推进工作。",
            f"本月，各地纷纷开展生产竞赛，工人们你追我赶搞生产，农民们精耕细作夺丰收，生产形势一片向好。",
            f"进入{MONTH_NAMES[month]}以来，全国物价稳定，市场供应充足，老百姓的日子安稳，大家都在各自的岗位上认真工作。",
        ]
        if year < 1958:
            fallback_texts.append("农村里互助组和合作社发展得很快，几家几户凑在一起干活，生产效率提高了不少，农民们的日子也比解放前好过了。")
            fallback_texts.append(f"解放初期，百废待兴，各行各业都在恢复生产。工人们抢修机器，农民们整理土地，大家齐心协力重建家园。")
        else:
            fallback_texts.append("人民公社里大家一起劳动一起吃饭，男女老少齐上阵，农田水利建设搞得热火朝天。")
            fallback_texts.append(f"在{MONTH_NAMES[month]}里，工业农业生产都取得了新成绩，各项工作稳步推进。")
        if fallback_index < len(fallback_texts):
            fb_text = fallback_texts[fallback_index]
        else:
            fb_text = fallback_texts[fallback_index % len(fallback_texts)] + f"这是{year_data.get('key_event', '社会主义建设')}的一个月份。"
        fb = simple_clean_text(fb_text, year)
        fb = deduplicate_emotion_words(fb)
        if fb and effective_length(fb) >= 60 and not is_too_similar(fb):
            news_items.append(fb)
            fallback_index += 1
        else:
            fallback_index += 1
            if fallback_index > 15:
                break

    seen_content = set()
    unique_items = []
    for item in news_items:
        item_key = re.sub(r'[^\u4e00-\u9fa5]', '', item)[:30]
        duplicate = False
        for seen in seen_content:
            if is_similar_title(item_key, seen):
                duplicate = True
                break
        if not duplicate:
            seen_content.add(item_key)
            unique_items.append(item)
    news_items = unique_items

    final_supplements = SUBSTANTIAL_SUPPLEMENTS[:]

    while len(news_items) < 6:
        key_evt = make_phrase_from_keywords(year_data.get('key_event', ''))
        fb_text = f"在{MONTH_NAMES[month]}里，全国人民紧密团结在党中央周围，{key_evt}，工人们在工厂里努力生产，农民们在田地里辛勤劳作，各项工作都在有序开展。"
        fb = simple_clean_text(fb_text, year)
        fb = deduplicate_emotion_words(fb)
        if fb and is_appropriate(fb):
            news_items.append(fb)
        else:
            break

    if len(news_items) > target_count:
        news_items = news_items[:target_count]
    while len(news_items) < 6:
        fb_text = f"进入{MONTH_NAMES[month]}，全国各项建设事业稳步推进，工农业生产都有新的进展。"
        fb = simple_clean_text(fb_text, year)
        fb = deduplicate_emotion_words(fb)
        if fb:
            news_items.append(fb)
        else:
            break
    news_items = news_items[:8]

    suppl_rng = random.Random(f"{year}_{month}_suppl")
    used_suppls = set()
    padded_items = []
    for idx, item in enumerate(news_items):
        is_manual_item = (idx == 0 and bool(manual_text))
        item = item.rstrip("。！？，,；;：: ")
        item_eff_len = effective_length(item)
        attempts = 0
        if not is_manual_item:
            while item_eff_len < 65 and attempts < 5:
                available = [s for s in final_supplements if s not in used_suppls]
                if not available:
                    available = final_supplements[:]
                    used_suppls.clear()
                suppl = suppl_rng.choice(available)
                used_suppls.add(suppl)
                item = item + "。" + suppl
                item = simple_clean_text(item, year)
                item = deduplicate_emotion_words(item)
                item_eff_len = effective_length(item)
                attempts += 1
        item = clean_hollow_endings(item, is_major_event=is_manual_item)
        padded_items.append(item)
    news_items = padded_items

    final_parts = [news_items[0]]
    trans_rng = random.Random(f"{year}_{month}_trans")
    available_trans = TRANSITIONS[:]
    for i, item in enumerate(news_items[1:]):
        if not available_trans:
            available_trans = TRANSITIONS[:]
        idx = trans_rng.randint(0, len(available_trans) - 1)
        trans = available_trans.pop(idx)
        final_parts.append(trans + item)
    final_text = "".join(final_parts)

    first_title = news_items[0]
    first_title = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z]+', '', first_title)
    if first_title and first_title[-1] in "。！？":
        first_title = first_title[:-1]
    if len(first_title) > 30:
        title = first_title[:30] + "..."
    else:
        title = first_title

    final_text = clean_broadcast_text(final_text, year, month)

    final_supplements_post = SUBSTANTIAL_SUPPLEMENTS[:]
    post_rng = random.Random(f"{year}_{month}_postpad")
    trans_list = ['另外，', '还有一条消息，', '再来看一条消息，', '说到这里，', '与此同时，']
    split_news = [final_text]
    for trans in trans_list:
        new_split = []
        for item in split_news:
            parts = item.split(trans)
            new_split.append(parts[0])
            for p in parts[1:]:
                new_split.append(trans + p)
        split_news = new_split
    used_post_suppls = set(used_suppls)
    padded_news = []
    for idx, item in enumerate(split_news):
        prefix_trans = ""
        body = item
        for trans in trans_list:
            if item.startswith(trans):
                prefix_trans = trans
                body = item[len(trans):]
                break
        is_first_segment = (idx == 0 and not prefix_trans)
        is_major = bool(manual_text) and is_first_segment
        body_eff = effective_length(body)
        attempts = 0
        while not is_major and body_eff < 50 and attempts < 5:
            available_post = [s for s in final_supplements_post if s not in used_post_suppls]
            if not available_post:
                available_post = final_supplements_post[:]
                used_post_suppls.clear()
            suppl = post_rng.choice(available_post)
            used_post_suppls.add(suppl)
            body = body.rstrip("。！？，,；;：: ") + "。" + suppl
            body = simple_clean_text(body, year)
            body = deduplicate_emotion_words(body)
            body_eff = effective_length(body)
            attempts += 1
        body = clean_hollow_endings(body, is_major_event=is_major)
        padded_news.append(prefix_trans + body)
    final_text = "".join(padded_news)
    final_text = simple_clean_text(final_text, year)
    final_text = fix_missing_punctuation(final_text)
    final_text = normalize_price_spacing(final_text)
    final_text = convert_all_decimal_prices(final_text)
    final_text = remove_consecutive_duplicate_sentences(final_text)
    final_text = arabic_to_chinese_small(final_text)
    final_text = deduplicate_emotion_words(final_text)
    final_text = clean_hollow_endings(final_text, is_major_event=bool(manual_text))
    final_text = re.sub(r'\s+', '', final_text)

    processed_items = []
    for item in news_items:
        item = normalize_price_spacing(item)
        item = convert_all_decimal_prices(item)
        item = remove_consecutive_duplicate_sentences(item)
        item = arabic_to_chinese_small(item)
        item = deduplicate_emotion_words(item)
        item = clean_hollow_endings(item, is_major_event=False)
        item = re.sub(r'\s+', '', item)
        processed_items.append(item)
    news_items = processed_items

    return final_text, title, news_items


def estimate_news_count(text):
    transitions_found = 0
    for t in TRANSITIONS:
        transitions_found += text.count(t)
    return transitions_found + 1


def main():
    print("正在加载知识库...")
    db_events = get_db_events()

    news_briefs = []
    global_seen_texts = set()
    stats = {
        "total_news": 0,
        "total_chars": 0,
        "opening_usage": Counter(),
        "months_with_prices": 0,
        "months_with_life": 0,
        "months_with_season": 0,
        "months_with_rmrb": 0,
        "format_errors": 0,
        "total_months": 0,
    }

    for year in range(1949, 1961):
        for month in range(1, 13):
            stats["total_months"] += 1
            text, title, raw_items = generate_month_news(year, month, db_events)

            if "。。" in text or "！！" in text or "？？" in text:
                stats["format_errors"] += 1

            item_count = len(raw_items)
            stats["total_news"] += item_count

            month_has_prices = bool(get_prices_for_year(year))
            month_has_life = bool(get_life_scenes_for_year(year))
            month_has_season = bool(get_season_scene(month))
            has_rmrb_date = any(get_rmrb_for_date(year, month, d) for d in DATE_FULL_DAYS)
            has_rmrb_month = bool(get_rmrb_for_month(year, month))
            month_has_rmrb = has_rmrb_date or has_rmrb_month
            if month_has_prices:
                stats["months_with_prices"] += 1
            if month_has_life:
                stats["months_with_life"] += 1
            if month_has_season:
                stats["months_with_season"] += 1
            if month_has_rmrb:
                stats["months_with_rmrb"] += 1

            for idx, item_text in enumerate(raw_items):
                item_text = item_text.strip()
                if not item_text:
                    continue
                # 全局去重：跳过与之前月份完全相同的文本
                text_key = item_text[:80]
                if text_key in global_seen_texts:
                    continue
                global_seen_texts.add(text_key)
                stats["total_chars"] += len(item_text)
                for o in ALL_OPENINGS:
                    cnt = item_text.count(o)
                    if cnt > 0:
                        stats["opening_usage"][o] += cnt

                if "。。" in item_text or "！！" in item_text or "？？" in item_text:
                    stats["format_errors"] += 1

                item_title = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z]+', '', item_text)
                if item_title and item_title[-1] in "。！？":
                    item_title = item_title[:-1]
                if len(item_title) > 30:
                    item_title = item_title[:30] + "..."

                est_duration = max(20, min(120, len(item_text) / 3.5))

                seg_id = f"news_{year}_{month:02d}_{idx+1:02d}"
                news_briefs.append({
                    "id": seg_id,
                    "type": "news_brief",
                    "year": year,
                    "month": month,
                    "index": idx + 1,
                    "text": item_text,
                    "title": item_title,
                    "duration": round(est_duration, 1),
                    "enterPoints": [0],
                    "signalQuality": 0.85,
                    "volume": 0.82
                })

    output = {
        "_meta": {
            "version": "4.0",
            "demo_range": "1949-1960",
            "coverage": "每月3-5条独立新闻，每条2-3分钟，融合知识库事件、物价、生活场景、季节描写",
            "created_at": "2026-07-01",
            "note": "使用knowledge_base.py解析12万字知识库生成，每条新闻独立输出，id格式news_YYYY_MM_NN。"
        },
        "news_briefs": news_briefs
    }

    with open(OUTPUT_SCRIPTS, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("✅ 生成完成！")
    print("=" * 70)
    print(f"📂 输出文件: {OUTPUT_SCRIPTS}")
    print(f"📅 覆盖月份: {stats['total_months']} 个月 (1949-01 至 1960-12)")
    print(f"📰 总新闻条目数: {stats['total_news']} 条")
    print(f"📝 平均每篇字数: {stats['total_chars'] // stats['total_months']} 字")
    print(f"📊 平均每条新闻字数: {stats['total_chars'] // max(1, stats['total_news'])} 字")
    print(f"🎤 使用开场白种类: {len([k for k, v in stats['opening_usage'].items() if v > 0])} / {len(ALL_OPENINGS)}")
    print(f"⚠️  格式错误数: {stats['format_errors']}")
    print()
    print("📚 知识库内容利用率:")
    print(f"  - 包含物价信息: {stats['months_with_prices']}/{stats['total_months']} 月 ({stats['months_with_prices']*100//stats['total_months']}%)")
    print(f"  - 包含生活场景: {stats['months_with_life']}/{stats['total_months']} 月 ({stats['months_with_life']*100//stats['total_months']}%)")
    print(f"  - 包含季节描写: {stats['months_with_season']}/{stats['total_months']} 月 ({stats['months_with_season']*100//stats['total_months']}%)")
    print(f"  - 包含人民日报: {stats['months_with_rmrb']}/{stats['total_months']} 月 ({stats['months_with_rmrb']*100//stats['total_months']}%)")
    print()
    total_openings = sum(stats['opening_usage'].values())
    print("🎤 开场白使用分布:")
    for opening, count in stats['opening_usage'].most_common():
        pct = count * 100 // max(1, total_openings)
        print(f"  {opening} × {count} ({pct}%)")

    print()
    print("=" * 70)
    print("📻 示例月份新闻审查")
    print("=" * 70)

    sample_keys = [(1949, 10), (1950, 10), (1951, 12), (1958, 9), (1959, 11), (1960, 1)]
    for brief in news_briefs:
        key = (brief['year'], brief['month'])
        if key in sample_keys:
            print(f"\n{'─' * 70}")
            print(f"【{brief['year']}年{MONTH_NAMES[brief['month']]}】 id={brief['id']} | 时长≈{brief['duration']}秒")
            print(f"标题: {brief['title']}")
            print(f"正文:")
            print(f"  {brief['text']}")
            future_years = re.findall(r'(\d{4})年', brief['text'])
            future_found = []
            for y_str in future_years:
                try:
                    y = int(y_str)
                    if y > brief['year'] + 1:
                        future_found.append(y)
                except ValueError:
                    pass
            if future_found:
                print(f"⚠️  发现未来年份: {future_found}")
            else:
                print(f"✅ 无未来年份")
            if "买一斤" in brief['text']:
                print(f"⚠️  物价表述问题: 发现重复斤字")
            else:
                print(f"✅ 物价表述正常")
            double_punc = re.findall(r'([。！？])\1+', brief['text'])
            if double_punc:
                print(f"⚠️  发现重复标点: {double_punc}")
            else:
                print(f"✅ 无重复标点")
            if brief['year'] in [1959, 1960, 1961]:
                if "越过越有奔头" in brief['text']:
                    print(f"⚠️  困难时期语调问题")
                else:
                    print(f"✅ 困难时期语调合适")
            print(f"{'─' * 70}")


if __name__ == "__main__":
    main()
