#!/usr/bin/env python3
"""
时光调频 · 年代感音频生成器（纯 Python 版本，无需 FFmpeg）

此版本使用纯 Python 实现年代感效果，不需要 FFmpeg。
如果已安装 FFmpeg，建议使用 generate_vintage_audio.py（效果更好）。

使用方法：
    python3 scripts/generate_vintage_audio_python.py

依赖安装：
    pip3 install edge-tts scipy numpy

功能：
    1. 使用 Edge-TTS 生成人声（免费，无需 API Key）
    2. 添加年代感效果（纯 Python 实现）
    3. 输出 mp3 文件
"""

import asyncio
import os
import sys
import wave
import struct
import argparse
import tempfile
from pathlib import Path

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")

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


def bandpass_filter(audio, sample_rate, low_freq, high_freq):
    """
    带通滤波（模拟老式收音机频响）

    参数：
        audio: 音频数据（numpy array）
        sample_rate: 采样率
        low_freq: 低频截止
        high_freq: 高频截止
    """
    try:
        from scipy.signal import butter, lfilter

        nyq = 0.5 * sample_rate
        low = low_freq / nyq
        high = high_freq / nyq

        # 防止频率超出范围
        low = max(0.001, min(0.999, low))
        high = max(0.001, min(0.999, high))

        if low >= high:
            return audio

        b, a = butter(5, [low, high], btype='band')
        filtered = lfilter(b, a, audio)

        return filtered
    except ImportError:
        print("⚠️ scipy 未安装，跳过带通滤波")
        return audio


def add_distortion(audio, drive=0.2):
    """
    添加谐波失真（模拟电子管温暖感）

    参数：
        audio: 音频数据
        drive: 失真强度（0.0-1.0）
    """
    # tanh 失真，模拟电子管效果
    return (3 * drive * audio) / (2 + 3 * drive * abs(audio))


def add_noise(audio, noise_level=0.015):
    """
    添加底噪（粉红噪音，模拟收音机底噪）

    参数：
        audio: 音频数据
        noise_level: 噪声强度（0.0-1.0）
    """
    import numpy as np

    noise = np.random.randn(len(audio)) * noise_level
    return audio + noise


def normalize(audio):
    """
    归一化音频，防止削波

    参数：
        audio: 音频数据
    """
    import numpy as np

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9  # 保留一点动态余量

    return audio


def apply_vintage_effect(audio, sample_rate, preset="vintage_70s"):
    """
    应用年代感效果

    参数：
        audio: 音频数据（numpy array）
        sample_rate: 采样率
        preset: 预设类型
    """
    import numpy as np

    # 年代感预设参数
    presets = {
        "vintage_50s": {
            "lowpass": 3000,
            "highpass": 300,
            "noise_level": 0.025,
            "distortion": 0.30,
        },
        "vintage_60s": {
            "lowpass": 3200,
            "highpass": 300,
            "noise_level": 0.020,
            "distortion": 0.25,
        },
        "vintage_70s": {
            "lowpass": 3400,
            "highpass": 350,
            "noise_level": 0.015,
            "distortion": 0.20,
        },
        "vintage_80s": {
            "lowpass": 4000,
            "highpass": 400,
            "noise_level": 0.010,
            "distortion": 0.15,
        },
    }

    if preset not in presets:
        print(f"⚠️ 未知预设 {preset}，使用 vintage_70s")
        preset = "vintage_70s"

    params = presets[preset]

    print(f"   📻 正在应用 {preset} 年代感效果...")
    print(f"   带通: {params['highpass']}Hz - {params['lowpass']}Hz")
    print(f"   底噪: {params['noise_level']}")
    print(f"   失真: {params['distortion']}")

    # 1. 带通滤波
    audio = bandpass_filter(audio, sample_rate, params['highpass'], params['lowpass'])

    # 2. 添加失真
    audio = add_distortion(audio, params['distortion'])

    # 3. 添加底噪
    audio = add_noise(audio, params['noise_level'])

    # 4. 归一化
    audio = normalize(audio)

    return audio


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

    print(f"   🎙️ 正在生成 TTS 音频...")
    print(f"   音色: {voice}")
    print(f"   语速: {speed}")

    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        print(f"   ✅ TTS 音频已生成: {output_path}")
        return True
    except Exception as e:
        print(f"   ❌ TTS 生成失败: {e}")
        return False


def convert_to_wav(mp3_path, wav_path):
    """
    将 MP3 转换为 WAV（使用 pydub）

    如果 pydub 不可用，会跳过转换，直接读取 MP3
    """
    import numpy as np
    from scipy.io import wavfile

    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(mp3_path)
        audio = audio.set_frame_rate(24000).set_channels(1)
        audio.export(wav_path, format="wav")
        return True
    except ImportError:
        print("   ⚠️ pydub 未安装，尝试直接读取 MP3...")

        # 尝试直接读取（可能失败）
        try:
            sr, audio = wavfile.read(mp3_path)
            return True
        except:
            print("   ❌ 无法读取音频文件。请安装 pydub: pip3 install pydub")
            print("   或安装 FFmpeg 以获得更好支持: brew install ffmpeg")
            return False


def wav_to_mp3(wav_path, mp3_path, bitrate="128k"):
    """
    将 WAV 转换为 MP3（使用 pydub）

    如果 pydub 不可用，会跳过转换，保留 WAV 格式
    """
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(wav_path)
        audio.export(mp3_path, format="mp3", bitrate=bitrate)
        return True
    except ImportError:
        print("   ⚠️ pydub 未安装，保留 WAV 格式")
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
    import numpy as np
    from scipy.io import wavfile

    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 临时文件
    temp_dir = tempfile.gettempdir()
    tts_path = os.path.join(temp_dir, f"tts_temp_{os.getpid()}.mp3")
    wav_path = os.path.join(temp_dir, f"tts_temp_{os.getpid()}.wav")
    vintage_wav_path = os.path.join(temp_dir, f"vintage_temp_{os.getpid()}.wav")
    output_path = os.path.join(OUTPUT_DIR, f"vintage_{preset}.mp3")

    print(f"\n📁 输出文件: {output_path}")

    try:
        # 1. 生成 TTS 人声
        success = await generate_tts(text, tts_path, voice, speed)
        if not success:
            return False

        # 2. 转换为 WAV
        print(f"   🔄 正在转换音频格式...")
        if not convert_to_wav(tts_path, wav_path):
            return False

        # 3. 读取音频
        print(f"   📂 正在读取音频...")
        sr, audio = wavfile.read(wav_path)

        # 转换为单声道和 float
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        audio = audio.astype(np.float32) / 32768.0

        print(f"   采样率: {sr}Hz")
        print(f"   时长: {len(audio) / sr:.1f}秒")

        # 4. 应用年代感效果
        audio = apply_vintage_effect(audio, sr, preset)

        # 5. 保存为 WAV
        print(f"   💾 正在保存...")
        vintage_audio = (audio * 32767).astype(np.int16)
        wavfile.write(vintage_wav_path, sr, vintage_audio)

        # 6. 转换为 MP3
        print(f"   🎵 正在导出 MP3...")
        wav_to_mp3(vintage_wav_path, output_path)

        print(f"   ✅ 年代感音频已生成: {output_path}")
        return True

    except ImportError as e:
        print(f"   ❌ 缺少依赖: {e}")
        print(f"   请运行: pip3 install edge-tts scipy numpy")
        return False

    except Exception as e:
        print(f"   ❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理临时文件
        for path in [tts_path, wav_path, vintage_wav_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass


def main():
    """主函数"""

    parser = argparse.ArgumentParser(
        description="时光调频 · 年代感音频生成器（纯 Python 版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    # 使用默认设置（70年代效果）
    python3 scripts/generate_vintage_audio_python.py

    # 生成所有年代版本
    python3 scripts/generate_vintage_audio_python.py --all-presets

    # 自定义音色和预设
    python3 scripts/generate_vintage_audio_python.py -v zh-CN-YunzeNeural -p vintage_50s

可用音色：
    zh-CN-YunyangNeural   - 标准中文男声（推荐）
    zh-CN-YunzeNeural     - 自然中文男声
    zh-CN-XiaoxiaoNeural  - 标准中文女声
    zh-CN-XiaoyiNeural    - 自然中文女声

可用预设：
    vintage_50s  - 50年代（最老旧）
    vintage_60s  - 60年代
    vintage_70s  - 70年代（推荐，参考音频风格）
    vintage_80s  - 80年代（稍清晰）
        """
    )
    parser.add_argument("--voice", "-v", default="zh-CN-YunyangNeural",
                        help="Edge-TTS 音色 ID")
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
    print("（纯 Python 版本）")
    print("=" * 50)

    # 检查依赖
    missing_deps = []
    try:
        import edge_tts
    except ImportError:
        missing_deps.append("edge-tts")

    try:
        import scipy
    except ImportError:
        missing_deps.append("scipy")

    try:
        import numpy
    except ImportError:
        missing_deps.append("numpy")

    if missing_deps:
        print(f"\n❌ 缺少依赖: {', '.join(missing_deps)}")
        print("请运行以下命令安装：")
        print("    pip3 install edge-tts scipy numpy")
        print("\n可选（更好的音频处理支持）：")
        print("    pip3 install pydub")
        print("\nmacOS 安装 ffmpeg（可选）：")
        print("    brew install ffmpeg")
        sys.exit(1)

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
    print("✨ 完成！")
    print(f"📂 请试听 {OUTPUT_DIR} 目录下的音频文件")
    print("=" * 50)


if __name__ == "__main__":
    main()
