#!/usr/bin/env python3
"""
生成合成音频素材并测试TTS音色：
1. 底噪素材（粉红噪音、磁带嘶声）
2. 呼号音乐（开场喇叭声）
3. 测试不同TTS音色
"""

import os
import sys
import json
import asyncio
import subprocess
import tempfile
import numpy as np
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("安装 edge-tts...")
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"], check=True)
    import edge_tts

FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if result.returncode == 0:
        FFMPEG = "ffmpeg"

SAMPLE_RATE = 22050
LIB_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib")
OUTPUT_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/output/voice_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_wav(audio, path, sr=SAMPLE_RATE):
    """保存为16位WAV"""
    audio = np.clip(audio, -1.0, 1.0)
    audio_int = (audio * 32767).astype(np.int16)
    from scipy.io import wavfile
    wavfile.write(path, sr, audio_int)
    print(f"  ✓ 已保存: {path} ({len(audio)/sr:.1f}秒)")


def generate_pink_noise(duration_sec, sr=SAMPLE_RATE):
    """生成粉红噪音（Voss-McCartney算法，模拟电子管底噪）"""
    n_samples = int(duration_sec * sr)
    n_octaves = 16
    octaves = np.random.randn(n_octaves, n_samples)
    for i in range(n_octaves):
        kernel_size = 2 ** (i + 1)
        octaves[i] = np.convolve(octaves[i], np.ones(kernel_size)/kernel_size, mode='same')
    pink = np.sum(octaves, axis=0)
    pink = pink / np.max(np.abs(pink)) * 0.3
    return pink


def generate_tape_hiss(duration_sec, sr=SAMPLE_RATE):
    """生成磁带嘶声（高频白噪音调制）"""
    n_samples = int(duration_sec * sr)
    white = np.random.randn(n_samples) * 0.15
    # 简单低通滤波
    b = [0.02, 0.05, 0.1, 0.2, 0.2, 0.2, 0.1, 0.05, 0.02]
    hiss = np.convolve(white, b, mode='same')
    hiss = hiss / np.max(np.abs(hiss)) * 0.2
    return hiss


def generate_am_static(duration_sec, sr=SAMPLE_RATE):
    """生成调幅广播静电噪声（脉冲+嘶声）"""
    n_samples = int(duration_sec * sr)
    base = np.random.randn(n_samples) * 0.1
    # 随机脉冲
    pulses = np.zeros(n_samples)
    n_pulses = int(duration_sec * 2)
    for _ in range(n_pulses):
        pos = np.random.randint(0, n_samples)
        width = np.random.randint(50, 500)
        pulses[pos:pos+width] += np.random.randn(width) * 0.3
    static = base + pulses
    static = static / np.max(np.abs(static)) * 0.25
    return static


def generate_signature_fanfare(duration_sec=8, sr=SAMPLE_RATE):
    """
    生成简单的开场喇叭呼号（模仿广播电台前奏）
    使用铜管乐器般的谐波合成
    """
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # 呼号旋律：简单的大三和弦上行→长音（模拟"当当当当"式开场）
    # 音符: C4 -> E4 -> G4 -> C5 -> G4
    melody_notes = [
        (261.63, 0.0, 0.4),  # C4
        (329.63, 0.45, 0.4),  # E4
        (392.00, 0.9, 0.4),   # G4
        (523.25, 1.35, 1.5),  # C5 (长音)
        (392.00, 2.9, 2.0),   # G4
    ]

    signal = np.zeros_like(t)

    for freq, start, dur in melody_notes:
        note_start = int(start * sr)
        note_end = int((start + dur) * sr)
        if note_end > len(t):
            note_end = len(t)
        n_samples = note_end - note_start

        tt = np.linspace(0, (note_end-note_start)/sr, note_end-note_start, endpoint=False)

        # 铜管音色模拟：基频 + 奇次谐波 + ADSR包络
        note = np.sin(2*np.pi*freq*tt) * 1.0
        note += np.sin(2*np.pi*freq*2*tt) * 0.4
        note += np.sin(2*np.pi*freq*3*tt) * 0.25
        note += np.sin(2*np.pi*freq*4*tt) * 0.15
        note += np.sin(2*np.pi*freq*5*tt) * 0.08

        # 轻微颤音
        vib = 1 + 0.003 * np.sin(2*np.pi*5*tt)
        note *= vib

        # ADSR 包络
        attack = int(0.05 * sr)
        decay = int(0.1 * sr)
        release = int(0.3 * sr)
        env = np.ones(n_samples)
        # Attack
        env[:attack] = np.linspace(0, 1, attack)
        # Decay
        if decay < n_samples - attack:
            env[attack:attack+decay] = np.linspace(1, 0.7, decay)
        # Release
        if release < n_samples:
            env[-release:] = np.linspace(env[-release-1] if release < n_samples else 1, 0, release)

        note = note * env * 0.4
        signal[note_start:note_end] += note

    # 混响模拟：简单的延迟反馈
    delay_samples = int(0.15 * sr)
    reverb = np.zeros_like(signal)
    for d in range(1, 5):
        offset = d * delay_samples
        if offset < len(signal):
            reverb[offset:] += signal[:-offset] * (0.3 ** d)
    signal = signal + reverb

    # 整体淡入淡出
    fade_samples = int(0.5 * sr)
    signal[:fade_samples] *= np.linspace(0, 1, fade_samples)
    signal[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    signal = signal / np.max(np.abs(signal)) * 0.5
    return signal


def generate_bridge_music(duration_sec=10, sr=SAMPLE_RATE):
    """生成简短的间隔音乐（轻音乐过渡）"""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)

    # 简单的弦乐垫音（长和弦）
    freqs = [220.0, 261.63, 329.63]  # A小调和弦
    signal = np.zeros_like(t)

    for freq in freqs:
        # 柔和音色：基频+低次谐波 + 慢颤音
        note = np.sin(2*np.pi*freq*t) * 0.3
        note += np.sin(2*np.pi*freq*2*t) * 0.1
        vib = 1 + 0.005 * np.sin(2*np.pi*4*t)
        note *= vib
        signal += note

    # 整体包络：缓慢起伏
    env = 0.5 + 0.5 * np.sin(2*np.pi*0.1*t - np.pi/2)
    signal = signal * env * 0.2

    # 淡入淡出
    fade = int(1.5 * sr)
    signal[:fade] *= np.linspace(0, 1, fade)
    signal[-fade:] *= np.linspace(1, 0, fade)

    return signal


def list_chinese_voices():
    """列出可用的中文TTS音色"""
    voices_result = subprocess.run(
        [sys.executable, "-m", "edge_tts", "--list-voices"],
        capture_output=True, text=True, timeout=30
    )
    voices = []
    for line in voices_result.stdout.split('\n'):
        if 'zh-CN' in line or 'zh-TW' in line or 'zh-HK' in line:
            parts = line.strip().split()
            if parts:
                voices.append(line.strip())
    return voices


async def test_voice(voice_name, text, output_path, rate="+0%"):
    """测试单个音色"""
    communicate = edge_tts.Communicate(text, voice_name, rate=rate)
    await communicate.save(str(output_path))
    return output_path


def apply_vintage_to_wav(input_wav, output_wav, preset="50s"):
    """对音频应用年代感效果"""
    presets = {
        "50s": {
            "lowpass": "3500",
            "highpass": "300",
            "distortion": "10",
            "bass_boost": "3",
            "noise_level": "0.08",
        },
        "70s": {
            "lowpass": "4000",
            "highpass": "250",
            "distortion": "5",
            "bass_boost": "2",
            "noise_level": "0.05",
        },
    }
    p = presets.get(preset, presets["50s"])

    filter_str = (
        f"highpass=f={p['highpass']},lowpass=f={p['lowpass']},"
        f"acompressor=threshold=-20dB:ratio=3:attack=5:release=50,"
        f"equalizer=f=800:t=q:w=1.5:g={p['bass_boost']},"
        f"acrusher=level_in=1:level_out=1:bits=10:mode=log"
    )

    cmd = [
        FFMPEG, "-y", "-i", str(input_wav),
        "-af", filter_str,
        "-acodec", "pcm_s16le", str(output_wav)
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)


def main():
    print("=" * 60)
    print("📻 时光调频 · 音频素材生成")
    print("=" * 60)

    # 1. 生成底噪素材
    print("\n🔊 生成底噪素材...")
    noise_dir = LIB_DIR / "noise"
    noise_dir.mkdir(parents=True, exist_ok=True)

    pink = generate_pink_noise(60)
    save_wav(pink, noise_dir / "pink_noise_radio.wav")

    tape = generate_tape_hiss(60)
    save_wav(tape, noise_dir / "tape_hiss.wav")

    am = generate_am_static(30)
    save_wav(am, noise_dir / "am_static.wav")

    # 2. 生成呼号音乐
    print("\n🎵 生成呼号音乐...")
    sig_dir = LIB_DIR / "bgm" / "signature"
    sig_dir.mkdir(parents=True, exist_ok=True)

    fanfare = generate_signature_fanfare(6)
    save_wav(fanfare, sig_dir / "opening_fanfare.wav")

    # 3. 生成间隔音乐
    print("\n🎵 生成间隔音乐...")
    bridge_dir = LIB_DIR / "bgm" / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)

    bridge = generate_bridge_music(12)
    save_wav(bridge, bridge_dir / "bridge_01.wav")

    # 4. 列出并测试中文TTS音色
    print("\n🗣️ 列出可用中文TTS音色...")
    voices = list_chinese_voices()
    print(f"找到 {len(voices)} 个中文音色:")
    for v in voices:
        print(f"  - {v}")

    # 选择几个代表性音色测试
    test_text = "各位听众朋友们，晚上好。今天是一九五零年，这里是中央人民广播电台。全国各地的听众同志们，在这次节目里，首先向大家报告重要新闻。"

    # 筛选男声/女声/不同风格的音色
    test_voices = []
    for v_line in voices:
        # 提取音色名称
        parts = v_line.split()
        if not parts:
            continue
        vname = parts[0]
        # 选几个代表性的：男女、新闻/故事风格
        if any(x in vname for x in ['Yunxi', 'Yunyang', 'Yunjian', 'Xiaoxiao', 'Xiaoyi', 'Yunxia']):
            if vname not in [x[0] for x in test_voices]:
                style = "男声" if any(x in vname for x in ['Yunxi', 'Yunyang', 'Yunjian']) else "女声"
                test_voices.append((vname, style))

    # 限定测试数量
    test_voices = test_voices[:8]
    print(f"\n🎙️ 测试 {len(test_voices)} 个代表性音色（语速参考：约200字/分钟）...")
    print(f"  参考语速: 190-200字/分钟 (Edge-TTS rate=+15%~+25%)")

    async def test_all_voices():
        for vname, style in test_voices:
            safe_name = vname.replace('-', '_')
            out_path = OUTPUT_DIR / f"voice_{safe_name}_p15.mp3"
            print(f"  测试: {vname} ({style}) rate=+15%")
            try:
                await test_voice(vname, test_text, out_path, rate="+15%")
            except Exception as e:
                print(f"    ⚠️ 失败: {e}")

    asyncio.run(test_all_voices())

    print("\n" + "=" * 60)
    print(f"✅ 素材已生成到: {LIB_DIR}")
    print(f"✅ 音色测试已保存到: {OUTPUT_DIR}")
    print("=" * 60)
    print("\n📋 关键参数总结（根据参考音频分析）：")
    print("  • 语速：约 190-200 字/分钟（Edge-TTS 需 +15%~+25% rate）")
    print("  • 底噪：-40dB 到 -46dB（粉红噪音）")
    print("  • 开场曲：5-8秒铜管呼号")
    print("  • 间隔音乐：8-12秒轻音乐过渡")
    print("  • 年代开场曲：")
    print("    - 50-70年代: 《东方红》旋律")
    print("    - 80年代起: 《歌唱祖国》旋律")

if __name__ == "__main__":
    main()
