#!/usr/bin/env python3
"""测试Edge-TTS所有中文音色，找出最接近年代广播播音员的"""
import asyncio
import sys
from pathlib import Path

try:
    import edge_tts
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"], check=True)
    import edge_tts

OUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/output/voice_compare")
OUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_TEXT = "中央人民广播电台。中央人民广播电台。各位听众朋友们，早上好。今天是一九七零年四月二十六日，现在是新闻和报纸摘要节目时间。首先报告国内要闻。"

async def main():
    voices = await edge_tts.list_voices()
    zh_voices = [v for v in voices if v["Locale"].startswith("zh")]

    print(f"找到 {len(zh_voices)} 个中文音色:\n")

    male = [v for v in zh_voices if v["Gender"] == "Male"]
    female = [v for v in zh_voices if v["Gender"] == "Female"]

    print(f"男声 ({len(male)}个):")
    for v in male:
        print(f"  {v['ShortName']} - {v.get('FriendlyName', '')}")
    print(f"\n女声 ({len(female)}个):")
    for v in female:
        print(f"  {v['ShortName']} - {v.get('FriendlyName', '')}")

    # 重点测试男声（新闻播音风格）
    test_list = []
    # 优先测试Yunxi/Yunyang/Yunjian等新闻风格男声
    for v in zh_voices:
        name = v["ShortName"]
        if any(k in name for k in ["Yunxi", "Yunyang", "Yunjian", "Yunze", "Yunhao", "Yunfeng"]):
            test_list.append(name)
    # 再测试女声
    for v in zh_voices:
        name = v["ShortName"]
        if any(k in name for k in ["Xiaoxiao", "Xiaoyi", "Xiaomo", "Yunxia", "Xiaoxuan", "Xiaohong"]):
            test_list.append(name)

    # 去重
    test_list = list(dict.fromkeys(test_list))
    print(f"\n🔊 测试 {len(test_list)} 个代表性音色（语速+15%，约200字/分钟）...")

    for voice_name in test_list:
        safe_name = voice_name.replace("-", "_")
        out_path = OUT_DIR / f"{safe_name}.mp3"
        if out_path.exists():
            print(f"  已存在: {voice_name}")
            continue
        print(f"  生成: {voice_name}...")
        try:
            communicate = edge_tts.Communicate(TEST_TEXT, voice_name, rate="+15%")
            await communicate.save(str(out_path))
            print(f"    ✓ 完成")
        except Exception as e:
            print(f"    ✗ 失败: {e}")

    print(f"\n✅ 测试音频保存在: {OUT_DIR}")
    print("请试听后选择最接近参考音频播音员的音色")

asyncio.run(main())
