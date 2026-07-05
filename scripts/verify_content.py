#!/usr/bin/env python3
"""
验证内容质量 - 自动检查所有programmatic验证点
"""
import json, os, sys, re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_json_valid():
    """检查JSON文件语法正确"""
    files = [
        os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"),
        os.path.join(PROJECT_ROOT, "audio-lib", "life-snippets.json"),
        os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool-scripts.json"),
    ]
    all_ok = True
    for f in files:
        try:
            with open(f, encoding='utf-8') as fp:
                json.load(fp)
            print(f"  ✅ {os.path.basename(f)}: JSON语法正确")
        except Exception as e:
            print(f"  ❌ {os.path.basename(f)}: {e}")
            all_ok = False
    return all_ok

def check_news_quantity():
    """AC-2: 每月3-5条新闻，总条数432-720"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    briefs = data['news_briefs']
    transitions = ['另外，', '还有一条消息，', '再来看一条消息，', '说到这里，', '与此同时，']
    total_stories = 0
    min_stories = 999
    max_stories = 0
    issues = []
    for b in briefs:
        text = b['text']
        count = 1
        for t in transitions:
            count += text.count(t)
        total_stories += count
        if count < 3:
            issues.append(f"  ⚠️  {b['id']} 只有{count}条新闻（要求3-5条）")
        min_stories = min(min_stories, count)
        max_stories = max(max_stories, count)
    print(f"  📰 总新闻条数: {total_stories} (要求432-720) {'✅' if 432<=total_stories<=720 else '❌'}")
    print(f"  📊 每月条数范围: {min_stories}-{max_stories}")
    for i in issues[:5]:
        print(i)
    return 432<=total_stories<=720 and min_stories>=3

def check_news_length():
    """AC-3: 平均每条新闻长度>80字，百科格式<5%，超短新闻0条"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    transitions = ['另外，', '还有一条消息，', '再来看一条消息，', '说到这里，', '与此同时，']
    total_len = 0
    total_count = 0
    wiki_format = 0
    super_short = 0
    for b in data['news_briefs']:
        text = b['text']
        news_items = [text]
        for trans in transitions:
            new_items = []
            for item in news_items:
                parts = item.split(trans)
                new_items.append(parts[0])
                for p in parts[1:]:
                    new_items.append(trans + p)
            news_items = new_items
        for item in news_items:
            item_clean = item.strip()
            item_len = len(re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', item_clean))
            if item_len < 40:
                super_short += 1
            total_len += len(item_clean)
            total_count += 1
            if re.search(r'\d+月\d+日[—\-－]', item_clean[:30]):
                wiki_format += 1
    avg = total_len / max(1, total_count)
    wiki_pct = wiki_format / max(1, total_count) * 100
    print(f"  📝 平均每条新闻长: {avg:.0f}字 (要求>80字) {'✅' if avg>80 else '❌'}")
    print(f"  📖 百科格式占比: {wiki_pct:.1f}% (要求<5%) {'✅' if wiki_pct<5 else '❌'}")
    print(f"  ⚡ 超短新闻(<40字有效内容): {super_short}条 (要求0) {'✅' if super_short==0 else '❌'}")
    return avg>80 and wiki_pct<5 and super_short==0

def check_date_variants():
    """AC-5: date_short>=8种变体"""
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
    import generate_date_tts as g
    shorts = set()
    for y in range(1949,1961):
        for m in range(1,13):
            shorts.add(g.build_short_text(y,m))
    print(f"  🎤 date_short变体: {len(shorts)}种 (要求>=8) {'✅' if len(shorts)>=8 else '❌'}")
    return len(shorts)>=8

def check_openings():
    """AC-6: 开场白>=12种，单种<15%"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    openings = [
        "新华社消息，", "本台消息，", "中央人民广播电台消息，", "同志们，",
        "各位听众同志们，", "最新消息，", "据人民日报报道，", "各位听众朋友们，",
        "乡亲们，同志们，", "中央台记者报道，", "来自前线的消息，", "好消息！",
        "同志们，报告大家一个好消息！", "广播里说，", "记者从有关方面获悉，",
        "今天的消息说，", "大家注意了，", "各位听众请注意，",
        "告诉大家一个好消息，", "特大喜讯！", "前线最新消息，",
        "各位老乡，", "听众朋友们，", "各位乡亲，",
    ]
    from collections import Counter
    cnt = Counter()
    total = 0
    for b in data['news_briefs']:
        text = b['text']
        for op in openings:
            if op in text:
                cnt[op] += 1
                total += 1
    if total == 0:
        print("  ❌ 未检测到开场白")
        return False
    max_pct = max(c/ total for c in cnt.values()) * 100
    print(f"  🎬 开场白种类: {len(cnt)}种 (要求>=12) {'✅' if len(cnt)>=12 else '❌'}")
    print(f"  📊 单种最高占比: {max_pct:.0f}% (要求<15%) {'✅' if max_pct<15 else '❌'}")
    return len(cnt)>=12 and max_pct<15

def check_format_errors():
    """AC-7: 双句号为0，外国事件为0，句子连写无标点问题为0"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    double_period = 0
    runon_sentence = 0
    foreign_keywords = ['B-50', '超级堡垒', '环球飞行', '欧洲经济共同体', '共同市场', '北约', '华约', '马歇尔计划']
    foreign_count = 0
    
    for b in data['news_briefs']:
        text = b['text']
        if '。。' in text:
            double_period += text.count('。。')
        for kw in foreign_keywords:
            if kw in text:
                foreign_count += 1
        runon_patterns = [
            r'[\u4e00-\u9fa5]{2,}纪录这是',
            r'[\u4e00-\u9fa5]{2,}消息这是',
            r'[\u4e00-\u9fa5]{2,}胜利这是',
            r'[\u4e00-\u9fa5]{2,}成功这是',
            r'[\u4e00-\u9fa5]{2,}完成这是',
            r'[\u4e00-\u9fa5]{2,}通车这是',
        ]
        for pat in runon_patterns:
            runon_sentence += len(re.findall(pat, text))
        if not text.endswith(('。', '！', '？')):
            runon_sentence += 1
    
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "life-snippets.json"), encoding='utf-8') as f:
        life = json.load(f)
    for s in life['life_snippets']:
        text = s['text']
        if '。。' in text:
            double_period += text.count('。。')
        for kw in foreign_keywords:
            if kw in text:
                foreign_count += 1
        if not text.endswith(('。', '！', '？')):
            runon_sentence += 1
    
    print(f"  🔧 双句号错误: {double_period}处 (要求0) {'✅' if double_period==0 else '❌'}")
    print(f"  🌍 外国无关事件: {foreign_count}处 (要求0) {'✅' if foreign_count==0 else '❌'}")
    print(f"  🔗 句子连写无标点: {runon_sentence}处 (要求0) {'✅' if runon_sentence==0 else '❌'}")
    return double_period==0 and foreign_count==0 and runon_sentence==0

def check_life_snippets():
    """AC-8: 生活片段>=144条，每条80-250字"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "life-snippets.json"), encoding='utf-8') as f:
        life = json.load(f)
    snippets = life['life_snippets']
    short_count = sum(1 for s in snippets if len(s['text']) < 80)
    long_count = sum(1 for s in snippets if len(s['text']) > 250)
    pre_58_sheyuan = sum(1 for s in snippets if s['year']<1958 and '社员' in s['text'])
    print(f"  🏠 生活片段总数: {len(snippets)}条 (要求>=144) {'✅' if len(snippets)>=144 else '❌'}")
    print(f"  📏 过短(<80字): {short_count}条 {'✅' if short_count==0 else '❌'}")
    print(f"  📏 过长(>250字): {long_count}条 {'✅' if long_count==0 else '❌'}")
    print(f"  👥 1958年前社员称谓: {pre_58_sheyuan}处 (要求0) {'✅' if pre_58_sheyuan==0 else '❌'}")
    return len(snippets)>=144 and short_count==0 and long_count==0 and pre_58_sheyuan==0

def check_knowledge_usage():
    """AC-4: 知识库利用率>=60%月份包含生活/物价/季节内容"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    has_life = 0
    has_price = 0
    has_season = 0
    total = len(data['news_briefs'])
    price_kws = ['元一斤', '元/斤', '大约', '物价', '工资', '斤大米', '斤猪肉', '分钱', '毛钱', '块钱']
    season_kws = ['春天', '夏天', '秋天', '冬天', '春耕', '麦收', '丰收', '寒冬', '初春', '初秋', '隆冬', '金秋', '盛夏', '初夏']
    life_kws = ['粮票', '布票', '大喇叭', '露天电影', '小人书', '合作社', '互助组', '中山装', '列宁装', '供销社', '凭票供应']
    for b in data['news_briefs']:
        t = b['text']
        if any(k in t for k in price_kws): has_price += 1
        if any(k in t for k in season_kws): has_season += 1
        if any(k in t for k in life_kws): has_life += 1
    print(f"  📚 含物价内容: {has_price}/{total}月 ({has_price/total*100:.0f}%)")
    print(f"  🌤 含季节描写: {has_season}/{total}月 ({has_season/total*100:.0f}%)")
    print(f"  👪 含生活关键词: {has_life}/{total}月 ({has_life/total*100:.0f}%)")
    covered = len(set(
        [b['id'] for b in data['news_briefs'] if any(k in b['text'] for k in price_kws+season_kws+life_kws)]
    ))
    print(f"  📊 知识库内容覆盖: {covered}/{total}月 ({covered/total*100:.0f}%) (要求>=60%) {'✅' if covered/total>=0.6 else '❌'}")
    return covered/total>=0.6

def check_shallow_content():
    """检查内容空洞问题 - 情绪词堆砌无实质内容"""
    with open(os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json"), encoding='utf-8') as f:
        data = json.load(f)
    shallow_count = 0
    shallow_patterns = [
        r'欢欣鼓舞[^。]{0,15}扬眉吐气',
        r'为建设新中国而努力奋斗[^。]{0,10}$',
        r'干劲十足[^。]{0,15}建设热情',
    ]
    shallow_examples = []
    for b in data['news_briefs']:
        text = b['text']
        for pat in shallow_patterns:
            if re.search(pat, text):
                sentences = re.split(r'[。！？]', text)
                for s in sentences:
                    if re.search(pat, s) and len(re.sub(r'[，、。！？\s]', '', s)) < 25:
                        shallow_count += 1
                        if len(shallow_examples) < 3:
                            shallow_examples.append(f"  ⚠️  {b['id']}: ...{s[-40:]}")
                        break
    print(f"  📭 内容空洞(情绪词无实质): {shallow_count}处 (要求0) {'✅' if shallow_count==0 else '❌'}")
    for ex in shallow_examples:
        print(ex)
    return shallow_count == 0

def main():
    print("="*60)
    print("时光调频 · 内容质量自动验证")
    print("="*60)
    print()
    results = []
    print("【1】JSON语法检查")
    results.append(("JSON语法", check_json_valid()))
    print()
    print("【2】新闻数量检查 (AC-2)")
    results.append(("新闻数量", check_news_quantity()))
    print()
    print("【3】新闻长度检查 (AC-3)")
    results.append(("新闻长度", check_news_length()))
    print()
    print("【4】开场白多样性 (AC-6)")
    results.append(("开场白多样", check_openings()))
    print()
    print("【5】格式错误检查 (AC-7)")
    results.append(("格式错误", check_format_errors()))
    print()
    print("【6】date开场变体 (AC-5)")
    results.append(("date变体", check_date_variants()))
    print()
    print("【7】生活片段检查 (AC-8)")
    results.append(("生活片段", check_life_snippets()))
    print()
    print("【8】知识库利用率 (AC-4)")
    results.append(("知识库利用", check_knowledge_usage()))
    print()
    print("【9】内容质量深度检查")
    results.append(("内容深度", check_shallow_content()))
    print()
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"验证结果: {passed}/{total} 项通过")
    if passed == total:
        print("✅ 所有检查通过！")
    else:
        failed = [name for name, r in results if not r]
        print(f"❌ 未通过项: {', '.join(failed)}")
    print("="*60)

if __name__ == "__main__":
    main()
