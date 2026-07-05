"""
时光调频知识库解析模块
======================
负责解析 docs/content/ 下的所有知识库文件，提供统一的数据访问接口，
并内置敏感词过滤机制确保生成内容符合官方表述要求。

对外接口：
- filter_text(text, year=None): 敏感词过滤
- get_year_data(year): 获取某年的完整数据
- get_events_for_month(year, month): 获取某年某月事件
- get_life_scenes_for_year(year): 获取某年代生活场景
- get_season_scene(month, variant=0): 获取季节场景描写
- get_prices_for_year(year): 获取某年物价
- get_rmrb_for_date(year, month, day): 获取人民日报当日内容
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# 注意：docs/content/ 为内容数据库，未开源，需自行准备
CONTENT_DIR = Path(__file__).parent.parent / "docs" / "content"
SENSITIVE_WORDS_PATH = CONTENT_DIR / "sensitive" / "sensitive-words.json"

_cache: Dict[str, Any] = {}
_sensitive_data: Optional[Dict] = None


def _load_sensitive_words() -> Dict:
    global _sensitive_data
    if _sensitive_data is not None:
        return _sensitive_data
    try:
        with open(SENSITIVE_WORDS_PATH, "r", encoding="utf-8") as f:
            _sensitive_data = json.load(f)
    except Exception:
        _sensitive_data = {"words": []}
    return _sensitive_data


def _read_file(filename: str) -> str:
    path = CONTENT_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _h2_iter(text: str):
    pat = re.compile(r"^##\s+([^#].*)$", re.MULTILINE)
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield title, text[start:end]


def _h3_iter(section: str):
    pat = re.compile(r"^###\s+([^#].*)$", re.MULTILINE)
    matches = list(pat.finditer(section))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        yield title, section[start:end]


def _h4_iter(section: str):
    pat = re.compile(r"^####\s+([^#].*)$", re.MULTILINE)
    matches = list(pat.finditer(section))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section)
        yield title, section[start:end]


def _parse_list_items(text: str) -> List[str]:
    items = []
    for part in re.split(r"[、，,；;]", text):
        part = part.strip()
        if part:
            items.append(part)
    return items


def filter_text(text: str, year: int = None, keep_era_terms: bool = False) -> str:
    """
    对文本进行敏感词过滤：
    - 一级黑词（level=1）：有replacement则替换，无replacement则删除包含该词的句子/段落
    - 二级红词（level=2）：按replacement替换，后见之明词/灾难词按规则处理
    - 1949-1960特殊处理：瓜菜代场景改写、饥饿相关负面描述去除、美帝在抗美援朝语境保留
    - 穿越词汇（GDP、互联网、手机等）一律删除或替换
    - keep_era_terms=True时（用于解析1949-1960年原始历史资料）：保留当时正常年代术语，不替换level=2中正常词汇
    """
    if not text:
        return ""
    data = _load_sensitive_words()
    words = data.get("words", [])
    level1_words = sorted([w for w in words if w.get("level") == 1], key=lambda x: -len(x["word"]))
    level2_words = sorted([w for w in words if w.get("level") == 2], key=lambda x: -len(x["word"]))

    ERA_TERMS_TO_KEEP = {"反革命", "反动派", "三反", "五反", "国民党反动派"}

    result = text

    for w in level1_words:
        word = w["word"]
        repl = w.get("replacement", "")
        if repl and word in result:
            result = result.replace(word, repl)

    hindsight_replacements = [
        ("那时候", "这会儿"),
        ("当时", "现在"),
        ("后来", ""),
        ("众所周知", ""),
        ("回首", ""),
        ("读者们不知道", ""),
        ("多年以后", ""),
        ("这场战争后来", ""),
        ("这首歌后来成为经典", "请听歌曲"),
        ("遗憾的是", ""),
        ("具有历史意义", ""),
    ]
    for word, repl in hindsight_replacements:
        result = result.replace(word, repl)

    if year is not None and 1949 <= year <= 1960:
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

    keep_meidi = (year is not None and 1950 <= year <= 1953)

    if not keep_meidi and not keep_era_terms:
        result = result.replace("美帝国主义", "美国")
        result = result.replace("美帝", "美国")

    for w in level2_words:
        word = w["word"]
        if keep_era_terms and word in ERA_TERMS_TO_KEEP:
            continue
        if word in ("美帝", "美帝国主义") and (keep_meidi or keep_era_terms):
            continue
        repl = w.get("replacement", "")
        if word in result:
            if repl:
                result = result.replace(word, repl)
            else:
                result = result.replace(word, "")

    sentences = re.split(r'(?<=[。！？；\n])', result)
    filtered_sentences = []
    for sent in sentences:
        sent_has_banned = False
        for w in level1_words:
            word = w["word"]
            repl = w.get("replacement", "")
            if not repl and word in sent:
                sent_has_banned = True
                break
        if not sent_has_banned:
            filtered_sentences.append(sent)
    result = "".join(filtered_sentences)

    result = re.sub(r'\s+', ' ', result)
    result = re.sub(r'([。！？，；：])\1+', r'\1', result)
    return result.strip()


def parse_yearly_events() -> Dict[int, Dict]:
    """解析 yearly-events.md，只解析1949-1960年数据"""
    text = _read_file("yearly-events.md")
    result: Dict[int, Dict] = {}

    for h2_title, h2_body in _h2_iter(text):
        year_match = re.match(r"(\d{4})年\s*[·・]\s*(.+)$", h2_title)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if year < 1949 or year > 1960:
            continue
        title = year_match.group(2).strip()

        year_data: Dict[str, Any] = {
            "year": year,
            "title": title,
            "key_event": "",
            "mood": "",
            "events": [],
            "prices": {},
            "life_keywords": [],
            "songs": [],
        }

        for h3_title, h3_body in _h3_iter(h2_body):
            if "基本信息" in h3_title:
                kw_match = re.search(r"\*\*年度关键词\*\*[：:]\s*(.+)", h3_body)
                if kw_match:
                    year_data["key_event"] = kw_match.group(1).strip()
                mood_match = re.search(r"\*\*整体情绪\*\*[：:]\s*(.+)", h3_body)
                if mood_match:
                    year_data["mood"] = mood_match.group(1).strip()

            elif "重大事件" in h3_title:
                event_pat = re.compile(
                    r"^(\s*\d+)\.\s*\*\*(.+?)\*\*[：:]\s*(.+)$", re.MULTILINE
                )
                ev_matches = list(event_pat.finditer(h3_body))

                for idx, ev_m in enumerate(ev_matches):
                    date_str = ev_m.group(2).strip()
                    ev_title_line = ev_m.group(3).strip()
                    ev_start = ev_m.end()
                    ev_end = ev_matches[idx + 1].start() if idx + 1 < len(ev_matches) else len(h3_body)
                    ev_body = h3_body[ev_start:ev_end]

                    month = None
                    day = None
                    month_m = re.search(r"(\d{1,2})月", date_str)
                    day_m = re.search(r"(\d{1,2})日", date_str)
                    if month_m:
                        month = int(month_m.group(1))
                    if day_m:
                        day = int(day_m.group(1))

                    detail_text = ""
                    detail_match = re.search(r"-\s*细节[：:]\s*(.*)", ev_body, re.DOTALL)
                    if detail_match:
                        raw_detail = detail_match.group(1)
                        detail_lines = []
                        for dl in raw_detail.split("\n"):
                            ds = dl.strip()
                            if ds and not ds.startswith("#"):
                                if ds.startswith("-") and "细节" not in ds:
                                    break
                                detail_lines.append(ds)
                        detail_text = " ".join(detail_lines).strip()

                    use_keep_era = 1949 <= year <= 1960
                    ev_title = filter_text(ev_title_line, year, keep_era_terms=use_keep_era)
                    ev_detail = filter_text(detail_text, year, keep_era_terms=use_keep_era)

                    year_data["events"].append({
                        "month": month,
                        "day": day,
                        "title": ev_title,
                        "detail": ev_detail,
                    })

            elif "物价" in h3_title:
                price_pat = re.compile(r"^-\s*(.+?)[：:]\s*(.+)$", re.MULTILINE)
                for pm in price_pat.finditer(h3_body):
                    item = pm.group(1).strip()
                    item = item.replace("*", "").strip()
                    price = pm.group(2).strip()
                    price = re.sub(r"[（(].*?[）)]", "", price).strip()
                    if item:
                        year_data["prices"][item] = price

            elif "歌曲" in h3_title:
                songs: List[str] = []
                for line in h3_body.split("\n"):
                    line = line.strip()
                    m = re.match(r"^\d+\.\s*(.+)$", line)
                    if not m:
                        continue
                    raw = m.group(1).strip()
                    name_match = re.search(r"[《\"](.+?)[》\"]", raw)
                    if name_match:
                        song_name = name_match.group(1).strip()
                    else:
                        song_name = re.sub(r"[（(].*?[）)]", "", raw).strip()
                        song_name = re.split(r"\s*[—\-–]\s*", song_name)[0].strip()
                    song_name = re.sub(r"[（(].*?[）)]", "", song_name).strip()
                    song_name = filter_text(song_name, year, keep_era_terms=use_keep_era)
                    if song_name and len(song_name) < 50:
                        songs.append(song_name)
                year_data["songs"] = songs

            elif "生活关键词" in h3_title:
                kw_text = h3_body.replace("-", " ").replace("\n", " ")
                kws = _parse_list_items(kw_text)
                year_data["life_keywords"] = [filter_text(k, year, keep_era_terms=use_keep_era) for k in kws if k]

        year_data["mood"] = filter_text(year_data["mood"], year, keep_era_terms=use_keep_era)
        year_data["key_event"] = filter_text(year_data["key_event"], year, keep_era_terms=use_keep_era)

        result[year] = year_data

    return result


def parse_life_keywords() -> Dict[str, List[Dict]]:
    """解析 life-keywords.md，重点提取1950年代、1960年代初"""
    text = _read_file("life-keywords.md")
    result: Dict[str, List[Dict]] = {
        "1950s": [],
        "1960s": [],
    }

    for h2_title, h2_body in _h2_iter(text):
        decade_m = re.match(r"(\d{3})0年代生活关键词", h2_title)
        if not decade_m:
            continue
        decade_key = decade_m.group(1) + "0s"
        if decade_key not in result:
            continue

        keywords_list: List[Dict] = []

        for h4_title, h4_body in _h4_iter(h2_body):
            kw_names_raw = h4_title.strip()
            kw_names = re.split(r"\s*[/／]\s*", kw_names_raw)
            kw_names = [n.strip() for n in kw_names if n.strip()]

            era = decade_key
            scene = ""
            memory_points: List[str] = []

            scene_match = re.search(r"\*\*场景\*\*[：:]\s*(.+?)(?=\n\s*-\s*\*\*|\Z)", h4_body, re.DOTALL)
            if scene_match:
                raw_scene = scene_match.group(1).strip()
                scene = re.sub(r"\s+", " ", raw_scene)

            if "困难时期" in kw_names_raw or "瓜菜代" in kw_names_raw:
                scene = "困难时期，大家想办法克服困难，共渡难关。"

            memory_match = re.search(r"\*\*记忆点\*\*[：:]\s*(.+)", h4_body)
            if memory_match:
                memory_points = _parse_list_items(memory_match.group(1))

            year_for_filter = 1955 if decade_key == "1950s" else 1960
            scene = filter_text(scene, year_for_filter, keep_era_terms=True)
            memory_points = [filter_text(m, year_for_filter, keep_era_terms=True) for m in memory_points if m]

            if scene:
                for kw_name in kw_names:
                    keywords_list.append({
                        "name": kw_name,
                        "era": era,
                        "scene": scene,
                        "memory_points": memory_points,
                    })

        result[decade_key] = keywords_list

    return result


def parse_seasons_weather() -> Dict[str, Any]:
    """解析 seasons-weather.md，返回季节场景和月份映射"""
    text = _read_file("seasons-weather.md")
    season_scenes: Dict[str, List[str]] = {
        "spring": [],
        "summer": [],
        "autumn": [],
        "winter": [],
    }

    season_map = [
        (r"春季描写", "spring"),
        (r"夏季描写", "summer"),
        (r"秋季描写", "autumn"),
        (r"冬季描写", "winter"),
    ]

    for h2_title, h2_body in _h2_iter(text):
        season_key = None
        for pat, key in season_map:
            if re.search(pat, h2_title):
                season_key = key
                break
        if not season_key:
            continue

        scene_section = ""
        for h3_title, h3_body in _h3_iter(h2_body):
            if "场景描写" in h3_title:
                scene_section = h3_body
                break

        for h4_title, h4_body in _h4_iter(scene_section):
            quote_lines = []
            for line in h4_body.split("\n"):
                stripped = line.strip()
                if stripped.startswith(">"):
                    quote_lines.append(stripped.lstrip("> ").strip())
            scene_text = " ".join(quote_lines).strip()
            scene_text = filter_text(scene_text)
            if scene_text:
                season_scenes[season_key].append(scene_text)

    month_to_scene: Dict[int, str] = {}
    month_season_map = {
        3: "spring", 4: "spring", 5: "spring",
        6: "summer", 7: "summer", 8: "summer",
        9: "autumn", 10: "autumn", 11: "autumn",
        12: "winter", 1: "winter", 2: "winter",
    }
    for month, season in month_season_map.items():
        scenes = season_scenes.get(season, [])
        if scenes:
            month_to_scene[month] = scenes[0]

    return {
        "spring": season_scenes["spring"],
        "summer": season_scenes["summer"],
        "autumn": season_scenes["autumn"],
        "winter": season_scenes["winter"],
        "month_to_scene": month_to_scene,
    }


def parse_prices_database() -> Dict[int, Dict[str, str]]:
    """解析 prices-database.md，按年份返回物价"""
    text = _read_file("yearly-events.md")
    result: Dict[int, Dict[str, str]] = {}

    for year in range(1949, 1961):
        result[year] = {}

    for h2_title, h2_body in _h2_iter(text):
        year_match = re.match(r"(\d{4})年", h2_title)
        if not year_match:
            continue
        year = int(year_match.group(1))
        if year < 1949 or year > 1960:
            continue
        for h3_title, h3_body in _h3_iter(h2_body):
            if "物价" in h3_title:
                price_pat = re.compile(r"^-\s*(.+?)[：:]\s*(.+)$", re.MULTILINE)
                for pm in price_pat.finditer(h3_body):
                    item = pm.group(1).strip()
                    item = item.replace("*", "").strip()
                    price = pm.group(2).strip()
                    price = re.sub(r"[（(].*?[）)]", "", price).strip()
                    if item:
                        result[year][item] = price

    return result


def parse_rmrb_archive() -> Dict[str, List[str]]:
    """解析 rmrb-archive.md，返回 {date_str: [paragraphs]}"""
    text = _read_file("rmrb-archive.md")
    result: Dict[str, List[str]] = {}

    for h2_title, h2_body in _h2_iter(text):
        date_m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", h2_title)
        if not date_m:
            continue
        year = int(date_m.group(1))
        month = int(date_m.group(2))
        day = int(date_m.group(3))
        if year < 1949 or year > 1960:
            continue
        date_key = f"{year:04d}-{month:02d}-{day:02d}"

        paragraphs: List[str] = []
        in_skip = False
        for line in h2_body.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("---"):
                in_skip = False
                continue
            if stripped.startswith("⚠️") or stripped.startswith("ℹ️") or stripped.startswith("> 来源") or stripped.startswith("> ⚠️"):
                in_skip = True
                continue
            if "广播稿生成" in stripped or "迁移到独立" in stripped or "素材仅供参考" in stripped or "旧版" in stripped:
                in_skip = True
                continue
            if stripped.startswith("###") or stripped.startswith("##"):
                in_skip = False
                continue
            if in_skip:
                continue
            if stripped.startswith(">"):
                content = stripped.lstrip("> ").strip()
                if content and not content.startswith("来源") and not content.startswith("⚠️"):
                    content = filter_text(content, year, keep_era_terms=1949 <= year <= 1960)
                    if content:
                        paragraphs.append(content)
            elif stripped.startswith("**【"):
                content = stripped.replace("**", "").strip()
                content = filter_text(content, year, keep_era_terms=1949 <= year <= 1960)
                if content:
                    paragraphs.append(content)
            elif re.match(r"^\d+\.\s*\*\*", stripped):
                content = re.sub(r"^\d+\.\s*", "", stripped)
                content = content.replace("**", "").strip()
                content = filter_text(content, year, keep_era_terms=1949 <= year <= 1960)
                if content:
                    paragraphs.append(content)

        if paragraphs:
            result[date_key] = paragraphs

    return result


def parse_all() -> None:
    global _cache
    _cache["yearly_events"] = parse_yearly_events()
    _cache["life_keywords"] = parse_life_keywords()
    _cache["seasons"] = parse_seasons_weather()
    _cache["prices_db"] = parse_prices_database()
    _cache["rmrb"] = parse_rmrb_archive()
    _load_sensitive_words()


def _ensure_cache() -> None:
    if not _cache:
        parse_all()


def _year_to_decade(year: int) -> str:
    if 1950 <= year <= 1959:
        return "1950s"
    elif 1960 <= year <= 1969:
        return "1960s"
    decade_start = (year // 10) * 10
    return f"{decade_start}s"


def get_year_data(year: int) -> Dict:
    """返回某年的所有数据（events, prices, life_keywords, songs, mood, key_event, title）"""
    _ensure_cache()
    ye = _cache["yearly_events"].get(year, {})
    prices = _cache["prices_db"].get(year, {})
    decade_key = _year_to_decade(year)
    lk_data = _cache["life_keywords"].get(decade_key, [])
    life_scene_names = [kw["name"] for kw in lk_data]
    life_keywords = list(set(ye.get("life_keywords", []) + life_scene_names))
    return {
        "year": year,
        "title": ye.get("title", ""),
        "key_event": ye.get("key_event", ""),
        "mood": ye.get("mood", ""),
        "events": ye.get("events", []),
        "prices": prices,
        "life_keywords": life_keywords,
        "songs": ye.get("songs", []),
    }


def get_events_for_month(year: int, month: int) -> List[Dict]:
    """返回某年某月的事件列表（优先匹配有明确月份的事件）"""
    _ensure_cache()
    ye = _cache["yearly_events"].get(year, {})
    events = ye.get("events", [])
    result = []
    for ev in events:
        if ev.get("month") == month:
            result.append(ev)
    if not result:
        for ev in events:
            if ev.get("month") is None:
                result.append(ev)
    return result


def get_life_scenes_for_year(year: int) -> List[Dict]:
    """返回某年代的生活场景列表"""
    _ensure_cache()
    decade_key = _year_to_decade(year)
    return _cache["life_keywords"].get(decade_key, [])


def get_season_scene(month: int, variant: int = 0, year: int = None) -> str:
    """返回某月份的季节场景描写，variant选择不同变体，year用于年代称谓替换"""
    _ensure_cache()
    month_season_map = {
        3: "spring", 4: "spring", 5: "spring",
        6: "summer", 7: "summer", 8: "summer",
        9: "autumn", 10: "autumn", 11: "autumn",
        12: "winter", 1: "winter", 2: "winter",
    }
    season = month_season_map.get(month, "spring")
    scenes = _cache["seasons"].get(season, [])
    if not scenes:
        return ""
    idx = variant % len(scenes)
    scene_text = scenes[idx]
    if year is not None and year < 1958:
        scene_text = scene_text.replace("社员们", "农民们")
        scene_text = scene_text.replace("社员同志", "乡亲们")
        scene_text = scene_text.replace("社员", "农民")
    return scene_text


def get_prices_for_year(year: int) -> Dict[str, str]:
    """返回某年的物价字典"""
    _ensure_cache()
    return _cache["prices_db"].get(year, {})


def get_rmrb_for_date(year: int, month: int, day: int) -> List[str]:
    """返回人民日报某日期内容列表，没有则返回空列表"""
    _ensure_cache()
    date_key = f"{year:04d}-{month:02d}-{day:02d}"
    return _cache["rmrb"].get(date_key, [])


def get_rmrb_for_month(year: int, month: int) -> List[str]:
    """返回人民日报某年某月任意可用内容（不限具体日期）"""
    _ensure_cache()
    rmrb = _cache["rmrb"]
    month_prefix = f"{year:04d}-{month:02d}-"
    result = []
    for date_key, paras in rmrb.items():
        if date_key.startswith(month_prefix):
            result.extend(paras)
    return result


if __name__ == "__main__":
    parse_all()

    print("=" * 60)
    print("时光调频 · 知识库解析测试报告")
    print("=" * 60)

    print("\n【1】1949-1960年事件统计（要求：每年至少3个事件）")
    all_ok = True
    for y in range(1949, 1961):
        yd = get_year_data(y)
        ev_count = len(yd["events"])
        status = "✓" if ev_count >= 3 else "✗"
        if ev_count < 3:
            all_ok = False
        print(f"  {status} {y}年【{yd['title']}】: {ev_count}个事件, key_event={yd['key_event'][:20]}...")
    print(f"  事件数量要求: {'通过' if all_ok else '未通过'}")

    print("\n【2】生活关键词统计（要求：1950年代至少15个）")
    lk50 = get_life_scenes_for_year(1955)
    lk60 = get_life_scenes_for_year(1960)
    print(f"  1950年代关键词: {len(lk50)}个 {'✓' if len(lk50)>=15 else '✗'}")
    for kw in lk50:
        print(f"    - {kw['name']}")
    print(f"  1960年代关键词: {len(lk60)}个")

    print("\n【3】四季场景统计（要求：每季节至少2个场景）")
    seasons = _cache["seasons"]
    for season_name, cn_name in [("spring", "春"), ("summer", "夏"), ("autumn", "秋"), ("winter", "冬")]:
        scenes = seasons[season_name]
        status = "✓" if len(scenes) >= 2 else "✗"
        print(f"  {status} {cn_name}季: {len(scenes)}个场景")

    print("\n【4】人民日报存档测试（要求：1950-10-19和1958-09-01存在）")
    rmrb_1950 = get_rmrb_for_date(1950, 10, 19)
    rmrb_1958 = get_rmrb_for_date(1958, 9, 1)
    print(f"  1950-10-19: {'✓ 有内容' if rmrb_1950 else '✗ 无内容'} ({len(rmrb_1950)}段)")
    print(f"  1958-09-01: {'✓ 有内容' if rmrb_1958 else '✗ 无内容'} ({len(rmrb_1958)}段)")
    if rmrb_1950:
        print(f"    首段预览: {rmrb_1950[0][:50]}...")

    print("\n【5】敏感词过滤测试")
    test_cases = [
        ("大饥荒年代粮食不够吃，大家饿肚子", 1960, "应替换为正面表述，无负面词"),
        ("GDP增长很快，互联网和手机普及了", None, "穿越词应被删除/替换"),
        ("美帝在朝鲜发动战争", 1951, "抗美援朝语境应保留美帝"),
        ("美帝在全球扩张", 1965, "非抗美援朝语境应替换为美国"),
        ("那时候大家都知道后来发生了什么", None, "后见之明词应被处理"),
    ]
    for text, year, desc in test_cases:
        filtered = filter_text(text, year)
        print(f"  测试: {desc}")
        print(f"    原文: {text}")
        print(f"    结果: {filtered}")

    print("\n" + "=" * 60)
    print("接口函数快速测试:")
    print("-" * 60)
    oct_events = get_events_for_month(1950, 10)
    print(f"get_events_for_month(1950,10): {len(oct_events)}个事件")
    spring_scene = get_season_scene(4, 0)
    print(f"get_season_scene(4,0): {spring_scene[:50]}...")
    prices_1955 = get_prices_for_year(1955)
    print(f"get_prices_for_year(1955): {list(prices_1955.keys())[:5]}...")
    print("=" * 60)
    print("测试完成!")
