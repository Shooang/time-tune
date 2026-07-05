#!/usr/bin/env python3
"""测试Edge-TTS中文音色"""
import asyncio
import sys
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("安装 edge-tts...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"], check=True)
    import edge_tts

OUTPUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/output/voice_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

async def main():
    # 列出所有中文音色
    voices = await edge_tts.list_voices()
    zh_voices = [v for v in voices if v["Locale"].startswith("zh")]

    print(f"找到 {len(zh_voices)} 个中文音色：")
    male_voices = []
    female_voices = []
    for v in zh_voices:
        gender = v.get("Gender", "")
        name = v["ShortName"]
        if gender == "Male":
            male_voices.append(name)
        else:
            female_voices.append(name)
        print(f"  {name} ({gender}) - {v.get('FriendlyName', '')}")

    test_text = "各位听众朋友们，晚上好。今天是一九五零年，这里是中央人民广播电台。全国各地的听众同志们，在这次节目里，首先向大家报告重要新闻。"

    # 测试几个代表性音色
    test_list = []
    # 男声
    for v in male_voices:
        if any(x in v for x in ["Yunxi", "Yunyang", "Yunjian", "Yunze", "Yunhao"]):
            test_list.append((v, "男声"))
    # 女声
    for v in female_voices:
        if any(x in v for x in ["Xiaoxiao", "Xiaoyi", "Xiaomo", "Yunxia", "Xiaoxuan"]):
            test_list.append((v, "女声"))

    print(f"\n测试 {len(test_list)} 个代表性音色（rate=+20%，约200字/分钟）...")

    for vname, style in test_list:
        for rate in ["+15%", "+20%", "+25%"]:
            safe_name = vname.replace('-', '_')
            out_path = OUTPUT_DIR / f"voice_{safe_name}_r{rate.replace('+','p').replace('%','')}.mp3"
            print(f"  生成: {vname} ({style}) rate={rate}")
            try:
                communicate = edge_tts.Communicate(test_text, vname, rate=rate)
                await communicate.save(str(out_path))
            except Exception as e:
                print(f"    ⚠️ 失败: {e}")

    print(f"\n✅ 测试音频保存到: {OUTPUT_DIR}")

asyncio.run(main())
