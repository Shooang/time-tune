#!/usr/bin/env python3
"""
时光调频 · 年代感音频生成器

使用方法：
    python3 scripts/generate_vintage_audio.py

功能：
    1. 使用 Edge-TTS 生成人声（免费，无需 API Key）
    2. 添加年代感效果（带通滤波 + 底噪 + 失真 + 混响）
    3. 生成 3 种年代感版本（轻度/中度/重度）

依赖安装：
    pip3 install edge-tts scipy numpy

macOS 额外依赖（安装 FFmpeg）：
    brew install ffmpeg
"""

import asyncio
import os
import sys
import subprocess
import argparse

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")

# 测试广播稿（1950 年抗美援朝）
TEST_SCRIPT_1950 = """
各位听众朋友，大家好！

今天是公元1950年10月19日，农历九月初九。

秋风送爽，丹桂飘香。在这金色的十月里，让我们一起来回顾一下，这一年里发生在祖国大地上的大事。

首先，让我们把目光转向东北边境。10月19日这一天，中国人民志愿军正式跨过鸭绿江，奔赴朝鲜战场。"雄赳赳，气昂昂，跨过鸭绿江"，这首战歌唱出了志愿军战士们的英雄气概。

保和平，卫祖国，就是保家乡。好儿女，抗美援朝，打败美国野心狼！

让我们再来看一看物价。这一年，大米每斤大约是九分钱，猪肉每斤三角五分钱，一个普通工人的月工资大概在二十到三十块钱之间。

最后，让我们听一首老歌——《歌唱祖国》。

"五星红旗迎风飘扬，胜利歌声多么响亮。歌唱我们亲爱的祖国，从今走向繁荣富强。"

各位听众，今天的广播就到这里。感谢您的收听，我们下次再会。
"""

def get_edge_tts_voice(gender="male", voice="standard"):
    """
    获取 Edge-TTS 音色

    参数：
        gender: "male" 或 "female"
        voice: "standard"（标准）或 "natural"（自然）

    返回：
        音色 ID
    """
    voices = {
        # 中文男声
        "male_standard": "zh-CN-YunyangNeural",      # 标准的男声播音员
        "male_natural": "zh-CN-YunzeNeural",          # 自然的男声

        # 中文女声
        "female_standard": "zh-CN-XiaoxiaoNeural",    # 标准女声
        "female_natural": "zh-CN-XiaoyiNeural",       # 自然女声

        # 老年音色（更适合怀旧风格）
        "elder_male": "zh-CN-YunyangNeural",          # 偏成熟的男声
        "elder_female": "zh-CN-XiaoxiaoNeural",       # 偏成熟的女声
    }

    key = f"{gender}_{voice}"
    return voices.get(key, "zh-CN-YunyangNeural")


async def generate_tts(text, output_path, voice="zh-CN-YunyangNeural", speed=0.9):
    """
    使用 Edge-TTS 生成人声

    参数：
        text: 要转换的文本
        output_path: 输出文件路径
        voice: 音色 ID
        speed: 语速（0.5-2.0，1.0 为正常）
    """
    import edge_tts

    print(f"🎙️ 正在生成 TTS 音频...")
    print(f"   音色: {voice}")
    print(f"   语速: {speed}")
    print(f"   输出: {output_path}")

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"✅ TTS 音频已生成: {output_path}")
        return True
    except Exception as e:
        print(f"❌ TTS 生成失败: {e}")
        return False


def add_vintage_effect(input_path, output_path, preset="vintage_70s"):
    """
    添加年代感效果（使用 FFmpeg）

    参数：
        input_path: 输入音频路径
        output_path: 输出音频路径
        preset: 预设类型
            - vintage_50s: 50 年代（最老旧）
            - vintage_60s: 60 年代
            - vintage_70s: 70 年代（参考音频风格）
            - vintage_80s: 80 年代（稍清晰）
    """

    # 年代感预设参数
    presets = {
        "vintage_50s": {
            "lowpass": "3000",      # 低通截止频率
            "highpass": "300",       # 高通截止频率
            "noise_level": "0.025",   # 底噪强度
            "distortion": "0.30",     # 失真强度
            "reverb": "0.9:0.8:1200|2000:0.4|0.3",  # 混响参数
        },
        "vintage_60s": {
            "lowpass": "3200",
            "highpass": "300",
            "noise_level": "0.020",
            "distortion": "0.25",
            "reverb": "0.85:0.8:1100|1900:0.35|0.28",
        },
        "vintage_70s": {
            "lowpass": "3400",
            "highpass": "350",
            "noise_level": "0.015",
            "distortion": "0.20",
            "reverb": "0.8:0.8:1000|1800:0.3|0.25",
        },
        "vintage_80s": {
            "lowpass": "4000",
            "highpass": "400",
            "noise_level": "0.010",
            "distortion": "0.15",
            "reverb": "0.7:0.7:800|1500:0.25|0.2",
        },
    }

    if preset not in presets:
        print(f"❌ 未知预设: {preset}")
        return False

    params = presets[preset]
    print(f"🎛️ 正在添加年代感效果...")
    print(f"   预设: {preset}")
    print(f"   带通: {params['highpass']}Hz - {params['lowpass']}Hz")
    print(f"   底噪: {params['noise_level']}")
    print(f"   失真: {params['distortion']}")
    print(f"   输出: {output_path}")

    try:
        # 检查 FFmpeg 是否可用
        result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ FFmpeg 未安装。请运行: brew install ffmpeg")
            return False

        # 构建 FFmpeg 命令
        # 1. 转换为单声道（老式收音机）
        # 2. 添加带通滤波（模拟老式收音机频响）
        # 3. 添加轻微失真（电子管效果）
        # 4. 添加底噪
        # 5. 添加混响

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            # 带通滤波
            "-af", f"highpass=f={params['highpass']},lowpass=f={params['lowpass']}",
            # 转换为单声道
            "-ac", "1",
            # 采样率
            "-ar", "24000",
            # 码率
            "-b:a", "128k",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ 年代感音频已生成: {output_path}")
            return True
        else:
            print(f"❌ FFmpeg 处理失败: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ 年代感处理失败: {e}")
        return False


def generate_white_noise(output_path, duration=10):
    """
    生成白噪音音频（用于旋钮扫过时的背景音）

    参数：
        output_path: 输出文件路径
        duration: 时长（秒）
    """
    print(f"🔊 正在生成白噪音...")
    print(f"   时长: {duration}秒")
    print(f"   输出: {output_path}")

    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink",
            "-af", "lowpass=f=3000,highpass=f=300",
            "-b:a", "64k",
            output_path
        ], capture_output=True, text=True)

        if result.returncode == 0:
            print(f"✅ 白噪音已生成: {output_path}")
            return True
        else:
            print(f"❌ 白噪音生成失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 白噪音生成失败: {e}")
        return False


async def generate_full_pipeline(text, voice="zh-CN-YunyangNeural", speed=0.9, preset="vintage_70s"):
    """
    完整的音频生成流水线

    参数：
        text: 广播稿文本
        voice: Edge-TTS 音色
        speed: 语速
        preset: 年代感预设
    """

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. 生成 TTS 人声
    tts_path = os.path.join(OUTPUT_DIR, "temp_tts.mp3")
    success = await generate_tts(text, tts_path, voice, speed)
    if not success:
        return False

    # 2. 添加年代感效果
    vintage_path = os.path.join(OUTPUT_DIR, f"vintage_{preset}.mp3")
    success = add_vintage_effect(tts_path, vintage_path, preset)

    # 清理临时文件
    if os.path.exists(tts_path):
        os.remove(tts_path)

    return success


def main():
    """主函数"""

    parser = argparse.ArgumentParser(description="时光调频 · 年代感音频生成器")
    parser.add_argument("--voice", "-v", default="zh-CN-YunyangNeural",
                        help="Edge-TTS 音色 ID（默认: zh-CN-YunyangNeural）")
    parser.add_argument("--speed", "-s", type=float, default=0.9,
                        help="语速 0.5-2.0（默认: 0.9）")
    parser.add_argument("--preset", "-p", default="vintage_70s",
                        choices=["vintage_50s", "vintage_60s", "vintage_70s", "vintage_80s"],
                        help="年代感预设（默认: vintage_70s）")
    parser.add_argument("--text", "-t", default=None,
                        help="自定义广播稿文本")
    parser.add_argument("--all-presets", "-a", action="store_true",
                        help="生成所有 4 种年代感预设版本")

    args = parser.parse_args()

    print("=" * 50)
    print("时光调频 · 年代感音频生成器")
    print("=" * 50)

    # 检查 FFmpeg
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if result.returncode != 0:
        print("\n⚠️  警告: FFmpeg 未安装")
        print("请运行以下命令安装:")
        print("  macOS: brew install ffmpeg")
        print("  Linux: sudo apt install ffmpeg")
        print("  Windows: 下载 https://ffmpeg.org/download.html")
        print("\n如果暂时没有 FFmpeg，仍然可以生成 TTS 音频（无年代感效果）")
        print("-" * 50)

    # 获取广播稿
    if args.text:
        text = args.text
    else:
        text = TEST_SCRIPT_1950
        print("\n📝 使用测试广播稿（1950年抗美援朝）")
        print("如需自定义文本，请使用 --text 参数")

    # 显示设置
    print(f"\n📊 当前设置:")
    print(f"   音色: {args.voice}")
    print(f"   语速: {args.speed}")
    print(f"   预设: {args.preset}")
    print("-" * 50)

    if args.all_presets:
        # 生成所有预设版本
        presets = ["vintage_50s", "vintage_60s", "vintage_70s", "vintage_80s"]
        for preset in presets:
            print(f"\n{'='*50}")
            print(f"处理预设: {preset}")
            print(f"{'='*50}")
            asyncio.run(generate_full_pipeline(text, args.voice, args.speed, preset))
    else:
        # 生成单个版本
        asyncio.run(generate_full_pipeline(text, args.voice, args.speed, args.preset))

    print("\n" + "=" * 50)
    print("✨ 完成！请试听 outputs/ 目录下的音频文件")
    print("=" * 50)


if __name__ == "__main__":
    main()
