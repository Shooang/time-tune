#!/usr/bin/env python3
"""
时光调频 · Demo音频池批量生成器

从 audio-pool-scripts.json 读取所有文本片段，批量生成TTS人声并添加年代感后处理。

使用方法：
    python3 scripts/generate_audio_pool.py
"""

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool-scripts.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "pool-generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VOICE = "zh-CN-YunyangNeural"
SPEED = 1.15


def bandpass_filter(audio, sample_rate, low_freq, high_freq):
    nyq = 0.5 * sample_rate
    low = max(0.001, low_freq / nyq)
    high = min(0.999, high_freq / nyq)
    if low >= high:
        return audio
    b, a = butter(4, [low, high], btype='band')
    return lfilter(b, a, audio)


def add_distortion(audio, drive=0.2):
    return (3 * drive * audio) / (2 + 3 * drive * np.abs(audio))


def generate_pink_noise(n_samples, sample_rate=24000, level=0.018):
    white = np.random.randn(n_samples).astype(np.float32)
    b, a = butter(2, 800 / (0.5 * sample_rate), btype='low')
    pink = lfilter(b, a, white)
    pink = pink / np.max(np.abs(pink)) * level
    return pink


def generate_crackle(n_samples, sample_rate=24000, rate=0.001, level=0.05):
    crackle = np.zeros(n_samples, dtype=np.float32)
    num_crackles = int(n_samples * rate)
    positions = np.random.randint(0, n_samples, num_crackles)
    for pos in positions:
        length = np.random.randint(5, 30)
        end = min(pos + length, n_samples)
        env = np.exp(-np.linspace(0, 5, end - pos))
        crackle[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return crackle


def generate_hum(n_samples, sample_rate=24000, level=0.005):
    t = np.linspace(0, n_samples / sample_rate, n_samples, dtype=np.float32)
    hum_50 = np.sin(2 * np.pi * 50 * t) * level
    hum_100 = np.sin(2 * np.pi * 100 * t) * level * 0.5
    return hum_50 + hum_100


def add_vintage_noise(audio, sample_rate, preset="vintage_70s"):
    presets = {
        "vintage_50s": {"noise_level": 0.028, "crackle_rate": 0.002, "hum_level": 0.007},
        "vintage_60s": {"noise_level": 0.022, "crackle_rate": 0.0015, "hum_level": 0.006},
        "vintage_70s": {"noise_level": 0.018, "crackle_rate": 0.001, "hum_level": 0.005},
        "vintage_ghost": {"noise_level": 0.05, "crackle_rate": 0.005, "hum_level": 0.015},
    }
    params = presets.get(preset, presets["vintage_70s"])
    
    pink = generate_pink_noise(len(audio), sample_rate, params["noise_level"])
    crackle = generate_crackle(len(audio), sample_rate, params["crackle_rate"], params["noise_level"] * 2)
    hum = generate_hum(len(audio), sample_rate, params["hum_level"])
    
    return audio + pink + crackle + hum


def apply_vintage_effect(audio, sample_rate, preset="vintage_70s"):
    presets = {
        "vintage_50s": {"lowpass": 3000, "highpass": 280, "distortion": 0.30, "noise_preset": "vintage_50s"},
        "vintage_60s": {"lowpass": 3200, "highpass": 300, "distortion": 0.25, "noise_preset": "vintage_60s"},
        "vintage_70s": {"lowpass": 3400, "highpass": 320, "distortion": 0.20, "noise_preset": "vintage_70s"},
        "vintage_ghost": {"lowpass": 2200, "highpass": 400, "distortion": 0.35, "noise_preset": "vintage_ghost"},
    }
    params = presets.get(preset, presets["vintage_70s"])
    
    audio = bandpass_filter(audio, sample_rate, params["highpass"], params["lowpass"])
    audio = add_distortion(audio, params["distortion"])
    audio = add_vintage_noise(audio, sample_rate, params["noise_preset"])
    
    fade_len = int(sample_rate * 0.05)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.88
    
    return audio


def clean_script(text):
    text = re.sub(r'\[(FANFARE|BELL|BRIDGE|SONG)[^\]]*\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'[（）【】]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


async def generate_tts(text, output_path, voice=VOICE, speed=SPEED):
    import edge_tts
    try:
        rate_str = f"+{int((speed-1)*100)}%" if speed > 1 else f"{int((speed-1)*100)}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"   Edge-TTS失败: {e}, 尝试macOS say命令...")
        return False


def load_audio_mp3(path):
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        wav_path = path.replace('.mp3', '_temp.wav')
        cmd = [ffmpeg_exe, '-y', '-i', path, '-ar', '24000', '-ac', '1', wav_path]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(wav_path):
            sr, audio = wavfile.read(wav_path)
            os.remove(wav_path)
            return sr, audio.astype(np.float32) / 32768.0
    except Exception as e:
        print(f"   FFmpeg转换失败: {e}")
    
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(path)
        audio = audio.set_frame_rate(24000).set_channels(1)
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        return 24000, samples / 32768.0
    except Exception as e:
        print(f"   pydub也失败: {e}")
        return None, None


def save_audio_wav(audio, sample_rate, path):
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(path, sample_rate, audio_int16)


def get_preset_for_year(year):
    if year < 1955:
        return "vintage_50s"
    elif year < 1965:
        return "vintage_60s"
    else:
        return "vintage_70s"


async def generate_segment(seg_id, text, year, preset_override=None, is_ghost=False):
    if is_ghost:
        preset = "vintage_ghost"
    else:
        preset = preset_override or get_preset_for_year(year)
    
    cleaned = clean_script(text)
    if not cleaned:
        print(f"   ⚠️ {seg_id}: 文本为空，跳过")
        return False
    
    print(f"\n🎙️ 生成 {seg_id} ({preset})")
    print(f"   文本: {cleaned[:50]}...")
    
    temp_dir = tempfile.gettempdir()
    tts_path = os.path.join(temp_dir, f"pool_tts_{seg_id}.mp3")
    
    success = await generate_tts(cleaned, tts_path)
    if not success:
        wav_path = os.path.join(temp_dir, f"pool_tts_{seg_id}.wav")
        safe_text = cleaned.replace('"', '\\"').replace("'", "\\'")
        say_voice = "Eddy"
        os.system(f'say -v {say_voice} -o "{wav_path}" --data-format=LEI16@22050 "{safe_text}"')
        if not os.path.exists(wav_path):
            print(f"   ❌ TTS全部失败")
            return False
        sr, audio = wavfile.read(wav_path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        audio = audio.astype(np.float32) / 32768.0
        if sr != 24000:
            from scipy.signal import resample
            num_samples = int(len(audio) * 24000 / sr)
            audio = resample(audio, num_samples).astype(np.float32)
            sr = 24000
        os.remove(wav_path)
    else:
        sr, audio = load_audio_mp3(tts_path)
        if sr is None:
            return False
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
    
    if audio is None or len(audio) == 0:
        print(f"   ❌ 音频加载失败")
        return False
    
    print(f"   原始时长: {len(audio)/sr:.1f}秒")
    
    audio = apply_vintage_effect(audio, sr, preset)
    
    out_path = os.path.join(OUTPUT_DIR, f"{seg_id}.wav")
    save_audio_wav(audio, sr, out_path)
    print(f"   ✅ 保存: {out_path} ({len(audio)/sr:.1f}秒)")
    
    try:
        if os.path.exists(tts_path):
            os.remove(tts_path)
    except:
        pass
    
    return True


async def main():
    print("=" * 60)
    print("时光调频 · Demo音频池批量生成器")
    print("=" * 60)
    
    try:
        import edge_tts
    except ImportError:
        print("⚠️ edge-tts未安装，将使用macOS say命令")
    
    with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    print(f"\n📂 输出目录: {OUTPUT_DIR}")
    print(f"🎙️ 使用音色: {VOICE}, 语速: x{SPEED}")
    
    total = 0
    success = 0
    
    # 1. 锚点大事件
    print(f"\n{'='*40}")
    print("📍 锚点大事件 (6段)")
    print(f"{'='*40}")
    for seg in pool["anchor_events"]:
        total += 1
        if await generate_segment(seg["id"], seg["script"], seg["year"]):
            success += 1
    
    # 2. 台呼
    print(f"\n{'='*40}")
    print("📻 台呼/报时 (8段)")
    print(f"{'='*40}")
    for seg in pool["station_ids"]:
        total += 1
        if await generate_segment(seg["id"], seg["text"], seg["year"]):
            success += 1
    
    # 3. 新闻短句
    print(f"\n{'='*40}")
    print("📰 新闻短句 (12段)")
    print(f"{'='*40}")
    for seg in pool["news_briefs"]:
        total += 1
        if await generate_segment(seg["id"], seg["text"], seg["year"]):
            success += 1
    
    # 4. 生活片段
    print(f"\n{'='*40}")
    print("🌤️ 天气/物价/生活 (8段)")
    print(f"{'='*40}")
    for seg in pool["life_snippets"]:
        total += 1
        if await generate_segment(seg["id"], seg["text"], seg["year"]):
            success += 1
    
    # 5. 小栏目
    print(f"\n{'='*40}")
    print("🎵 小栏目提示音 (4段)")
    print(f"{'='*40}")
    for seg in pool["jingles"]:
        total += 1
        if await generate_segment(seg["id"], seg["text"], seg["year"]):
            success += 1
    
    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{total}")
    print(f"📂 生成目录: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
