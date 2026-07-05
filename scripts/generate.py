#!/usr/bin/env python3
"""
时光调频 · 年代感音频一体化生成器

使用方法：
    # 从 JSON 脚本文件生成
    python3 scripts/generate.py --script scripts/test_scripts/1950_script.json

    # 直接传入文本生成（快速测试）
    python3 scripts/generate.py --text "各位听众大家好" --preset vintage_70s

依赖：
    pip3 install edge-tts pydub numpy scipy imageio-ffmpeg

功能：
    1. Edge-TTS 生成人声
    2. FFmpeg 后处理（带通滤波 + 失真 + 底噪 + 混响）
    3. 年代感预设（50s/60s/70s/80s）
    4. 输出 mp3
"""

import asyncio
import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

def get_ffmpeg():
    """获取 FFmpeg 路径（优先系统ffmpeg，其次imageio-ffmpeg）"""
    try:
        result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
        if result.returncode == 0:
            return "ffmpeg"
    except:
        pass
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None

FFMPEG = get_ffmpeg()

PRESETS = {
    "vintage_50s": {
        "lowpass": 2800,
        "highpass": 350,
        "noise_db": -38,
        "distortion": 0.35,
        "acrossover": 1200,
        "aslope": 0.4,
        "areflection": 0.25,
        "reverb_dry": 0.6,
        "reverb_wet": 0.4,
        "treble": -3,
        "bass": "+2",
        "compand": ".15:.1:−60/−40|−40/−20",
        "description": "50年代——最老旧，底噪大，频宽窄，失真重",
    },
    "vintage_60s": {
        "lowpass": 3000,
        "highpass": 350,
        "noise_db": -40,
        "distortion": 0.28,
        "acrossover": 1100,
        "aslope": 0.35,
        "areflection": 0.22,
        "reverb_dry": 0.65,
        "reverb_wet": 0.35,
        "treble": -2,
        "bass": "+1.5",
        "compand": ".12:.1:−60/−40|−40/−18",
        "description": "60年代——较老旧",
    },
    "vintage_70s": {
        "lowpass": 3400,
        "highpass": 300,
        "noise_db": -42,
        "distortion": 0.22,
        "acrossover": 1000,
        "aslope": 0.3,
        "areflection": 0.18,
        "reverb_dry": 0.7,
        "reverb_wet": 0.3,
        "treble": -1,
        "bass": "+1",
        "compand": ".1:.08:−60/−38|−38/−15",
        "description": "70年代——参考音频风格，中央台广播质感",
    },
    "vintage_80s": {
        "lowpass": 4000,
        "highpass": 250,
        "noise_db": -46,
        "distortion": 0.15,
        "acrossover": 800,
        "aslope": 0.2,
        "areflection": 0.12,
        "reverb_dry": 0.8,
        "reverb_wet": 0.2,
        "treble": 0,
        "bass": "+0.5",
        "compand": ".08:.06:−60/−35|−35/−12",
        "description": "80年代——稍清晰，底噪小，失真轻",
    },
}

async def generate_tts(text, output_path, voice="zh-CN-YunyangNeural", speed=0.9):
    """使用 Edge-TTS 生成人声"""
    import edge_tts

    print(f"🎙️ [1/3] 生成 TTS 音频...")
    print(f"   音色: {voice}  语速: {speed}")

    # 清理换行符，确保连续朗读
    clean_text = text.replace("\n\n", "。").replace("\n", "").strip()
    rate_str = f"{int(speed * 100 - 100):+d}%" if speed != 1.0 else "+0%"

    try:
        communicate = edge_tts.Communicate(clean_text, voice, rate=rate_str)
        await communicate.save(str(output_path))
        print(f"   ✅ TTS 生成完成: {output_path.name}")
        return True
    except Exception as e:
        print(f"   ❌ TTS 失败: {e}")
        return False

def add_vintage_effect(input_path, output_path, preset_name="vintage_70s"):
    """使用 FFmpeg 添加年代感效果"""
    if not FFMPEG:
        print("   ❌ FFmpeg 不可用，跳过年代感处理")
        import shutil
        shutil.copy(str(input_path), str(output_path))
        return False

    params = PRESETS[preset_name]
    print(f"🎛️  [2/3] 添加年代感效果 [{preset_name}]...")
    print(f"   {params['description']}")
    print(f"   频带: {params['highpass']}Hz - {params['lowpass']}Hz")
    print(f"   底噪: {params['noise_db']}dB  失真: {params['distortion']}")

    # 使用 filter_complex 方式，分两步处理避免滤镜链过长导致的解析错误
    # 步骤1: 基础处理（带通+压缩+混响+失真+均衡）
    # 步骤2: 混入底噪 + 最终归一化

    # 基础滤镜（处理人声）
    voice_filter = (
        f"pan=mono|c0=.5*c0+.5*c1,"
        f"highpass=f={params['highpass']},"
        f"lowpass=f={params['lowpass']},"
        f"acompressor=threshold=-18dB:ratio=3:attack=5:release=50:makeup=2,"
        f"aecho=0.8:0.7:{int(params['acrossover']*0.05)}|{int(params['acrossover']*0.1)}:{params['areflection']}|{params['areflection']*0.4},"
        f"equalizer=f=100:t=q:w=1.5:g={params['bass']},"
        f"equalizer=f=3500:t=q:w=1:g={params['treble']},"
        f"alimiter=limit=0.9"
    )

    # 先用基础滤镜处理
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        voice_tmp = tmp / "voice.mp3"

        cmd1 = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-af", voice_filter,
            "-ac", "1", "-ar", "24000", "-b:a", "128k",
            str(voice_tmp),
        ]
        r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=60)

        if r1.returncode != 0:
            print(f"   ⚠️ 基础滤镜失败，使用简化版...")
            return _add_vintage_effect_simple(input_path, output_path, params)

        # 生成底噪并混入
        noise_dur = 600  # 10分钟足够覆盖
        noise_tmp = tmp / "noise.wav"
        mixed_tmp = tmp / "mixed.mp3"

        # 生成粉红噪音
        cmd_noise = [
            FFMPEG, "-y",
            "-f", "lavfi", "-i", f"anoisesrc=d={noise_dur}:c=pink:r=24000:a=0.5",
            "-af", f"highpass=f=200,lowpass=f=4000,volume={params['noise_db']}dB",
            "-ac", "1", "-ar", "24000",
            str(noise_tmp),
        ]
        r2 = subprocess.run(cmd_noise, capture_output=True, text=True, timeout=30)

        if r2.returncode == 0:
            # 混入底噪
            cmd_mix = [
                FFMPEG, "-y",
                "-i", str(voice_tmp),
                "-i", str(noise_tmp),
                "-filter_complex",
                f"[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0,"
                f"loudnorm=I=-14:TP=-1:LRA=11,"
                f"alimiter=limit=0.95",
                "-ac", "1", "-ar", "24000", "-b:a", "128k",
                str(mixed_tmp),
            ]
            r3 = subprocess.run(cmd_mix, capture_output=True, text=True, timeout=60)

            if r3.returncode == 0 and mixed_tmp.exists() and mixed_tmp.stat().st_size > 1000:
                import shutil
                shutil.copy(str(mixed_tmp), str(output_path))
                print(f"   ✅ 年代感处理完成（含底噪）: {output_path.name}")
                return True

        # 底噪混失败，用无噪版本
        import shutil
        shutil.copy(str(voice_tmp), str(output_path))
        print(f"   ✅ 年代感处理完成（无额外底噪）: {output_path.name}")
        return True

def _add_vintage_effect_simple(input_path, output_path, params):
    """简化版年代感效果（备用方案）"""
    af_chain = (
        f"pan=mono|c0=.5*c0+.5*c1,"
        f"highpass=f={params['highpass']},lowpass=f={params['lowpass']},"
        f"acompressor=threshold=-20dB:ratio=4:attack=5:release=50,"
        f"aecho=0.8:0.7:{int(params['acrossover']*0.07)}:{params['areflection']},"
        f"loudnorm=I=-14:TP=-1:LRA=11"
    )

    cmd = [
        FFMPEG, "-y",
        "-i", str(input_path),
        "-af", af_chain,
        "-ac", "1",
        "-ar", "24000",
        "-b:a", "128k",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
        print(f"   ✅ 简化版年代感处理完成")
        return True
    else:
        print(f"   ❌ 后处理失败，保留原始TTS")
        print(f"   stderr: {result.stderr[-500:] if result.stderr else 'unknown'}")
        import shutil
        shutil.copy(str(input_path), str(output_path))
        return False

async def generate_from_script(script_path):
    """从 JSON 脚本文件生成"""
    with open(script_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    text = data["script"]
    voice = data.get("voice", "zh-CN-YunyangNeural")
    speed = data.get("speed", 0.9)
    preset = data.get("preset", "vintage_70s")
    year = data.get("year", "test")

    return await _generate(text, voice, speed, preset, year)

async def generate_from_text(text, preset="vintage_70s", voice="zh-CN-YunyangNeural", speed=0.9):
    """直接从文本生成"""
    return await _generate(text, voice, speed, preset, "custom")

async def _generate(text, voice, speed, preset, label):
    """核心生成流水线"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 输出文件路径
    if preset:
        final_name = f"vintage_{label}_{preset}.mp3"
    else:
        final_name = f"tts_{label}.mp3"
    tts_raw_name = f"tts_raw_{label}.mp3"

    final_path = OUTPUT_DIR / final_name
    tts_raw_path = OUTPUT_DIR / tts_raw_name

    print("=" * 60)
    print(f"📻 时光调频 · 年代感音频生成器")
    print("=" * 60)
    print(f"📝 脚本长度: {len(text)} 字 (约 {len(text)/200:.1f} 分钟)")
    print(f"🎚️ 预设: {preset} - {PRESETS.get(preset, {}).get('description', '')}")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # 步骤1: TTS 生成
        tts_path = tmp / "tts_raw.mp3"
        if not await generate_tts(text, tts_path, voice, speed):
            print("❌ TTS 生成失败")
            return None

        # 保存原始TTS供对比
        import shutil
        shutil.copy(str(tts_path), str(tts_raw_path))
        print(f"   💾 原始TTS已保存: {tts_raw_name}")

        # 步骤2: 年代感后处理
        vintage_path = tmp / "vintage.mp3"
        if preset and preset in PRESETS:
            add_vintage_effect(tts_path, vintage_path, preset)
        else:
            shutil.copy(str(tts_path), str(vintage_path))

        # 步骤3: 复制最终结果
        shutil.copy(str(vintage_path), str(final_path))

    print(f"🎵 [3/3] 完成！")
    print("-" * 60)
    print(f"📂 输出文件:")
    print(f"   原始TTS:  {tts_raw_path}")
    print(f"   年代感版: {final_path}")
    print("=" * 60)
    return final_path

def list_presets():
    """列出所有预设"""
    print("📻 时光调频 · 可用年代预设：")
    print()
    for name, p in PRESETS.items():
        print(f"  {name:15s} - {p['description']}")
        print(f"{'':17s} 频带 {p['highpass']}Hz-{p['lowpass']}Hz, 底噪 {p['noise_db']}dB")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="时光调频 · 年代感音频一体化生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/generate.py --script scripts/test_scripts/1950_script.json
  python3 scripts/generate.py --text "中央人民广播电台" --preset vintage_70s
  python3 scripts/generate.py --presets
        """
    )
    parser.add_argument("--script", "-i", help="JSON 脚本文件路径")
    parser.add_argument("--text", "-t", help="直接输入文本（快速测试）")
    parser.add_argument("--preset", "-p", default="vintage_70s",
                        choices=list(PRESETS.keys()),
                        help="年代感预设（默认 vintage_70s）")
    parser.add_argument("--voice", "-v", default="zh-CN-YunyangNeural",
                        help="Edge-TTS 音色（默认 zh-CN-YunyangNeural）")
    parser.add_argument("--speed", "-s", type=float, default=0.88,
                        help="语速（默认 0.88）")
    parser.add_argument("--presets", action="store_true", help="列出所有预设")
    parser.add_argument("--no-effect", action="store_true", help="只生成TTS，不加年代感效果")

    args = parser.parse_args()

    if args.presets:
        list_presets()
        return

    if not FFMPEG:
        print("⚠️ FFmpeg 未找到。请安装：pip3 install imageio-ffmpeg")
        print("   或系统安装：brew install ffmpeg / apt install ffmpeg")
        sys.exit(1)

    if args.script:
        script_path = Path(args.script)
        if not script_path.is_absolute():
            script_path = PROJECT_ROOT / args.script
        if not script_path.exists():
            print(f"❌ 脚本文件不存在: {script_path}")
            sys.exit(1)
        preset = None if args.no_effect else args.preset
        result = asyncio.run(generate_from_script(script_path))
    elif args.text:
        preset = None if args.no_effect else args.preset
        result = asyncio.run(generate_from_text(
            args.text, preset, args.voice, args.speed
        ))
    else:
        # 默认生成1950年测试音频
        default_script = PROJECT_ROOT / "scripts" / "test_scripts" / "1950_script.json"
        if default_script.exists():
            print(f"📂 使用默认脚本: {default_script.name}")
            preset = None if args.no_effect else args.preset
            result = asyncio.run(generate_from_script(default_script))
        else:
            parser.print_help()
            sys.exit(1)

    if result:
        print(f"\n✅ 生成成功！请打开试听: {result}")
    else:
        print("\n❌ 生成失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
