#!/usr/bin/env python3
"""
批量生成1949-1960年月度新闻TTS音频，带年代感后处理。
使用 edge-tts 生成语音，添加50年代老式广播效果。
"""
import asyncio
import json
import os
import sys
import tempfile
import shutil
import numpy as np
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "monthly-news-scripts.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "pool-generated")
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "docs", "design", "prototype", "public", "audio", "programs")

VOICE = "zh-CN-YunyangNeural"
SPEED = 0.90

def bandpass_filter(audio, sample_rate, low_freq, high_freq):
    from scipy.signal import butter, lfilter
    nyq = 0.5 * sample_rate
    low = max(0.001, low_freq / nyq)
    high = min(0.999, high_freq / nyq)
    if low >= high:
        return audio
    b, a = butter(4, [low, high], btype='band')
    return lfilter(b, a, audio)

def add_distortion(audio, drive=0.18):
    return (2.5 * drive * audio) / (1 + 2 * drive * np.abs(audio))

def generate_pink_noise(n_samples, sample_rate=24000, level=0.005):
    white = np.random.randn(n_samples).astype(np.float32)
    from scipy.signal import butter, lfilter
    b, a = butter(2, 700 / (0.5 * sample_rate), btype='low')
    pink = lfilter(b, a, white)
    pink = pink / np.max(np.abs(pink)) * level
    return pink

def generate_crackle(n_samples, sample_rate=24000, rate=0.0003, level=0.012):
    crackle = np.zeros(n_samples, dtype=np.float32)
    num_crackles = int(n_samples * rate)
    positions = np.random.randint(0, n_samples, num_crackles)
    for pos in positions:
        length = np.random.randint(3, 20)
        end = min(pos + length, n_samples)
        env = np.exp(-np.linspace(0, 4, end - pos))
        crackle[pos:end] += np.random.randn(end - pos).astype(np.float32) * env * level
    return crackle

def generate_hum(n_samples, sample_rate=24000, level=0.002):
    t = np.linspace(0, n_samples / sample_rate, n_samples, dtype=np.float32)
    hum_50 = np.sin(2 * np.pi * 50 * t) * level
    hum_100 = np.sin(2 * np.pi * 100 * t) * level * 0.4
    return hum_50 + hum_100

def apply_vintage_50s(audio, sample_rate):
    """50年代广播风格：较窄频带、轻微失真、极低噪底（适老化：人声清晰）"""
    audio = bandpass_filter(audio, sample_rate, 300, 3400)
    audio = add_distortion(audio, 0.15)
    pink = generate_pink_noise(len(audio), sample_rate, 0.005)
    crackle = generate_crackle(len(audio), sample_rate, 0.0003, 0.010)
    hum = generate_hum(len(audio), sample_rate, 0.002)
    audio = audio + pink + crackle + hum
    fade_len = int(sample_rate * 0.04)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9
    return audio

def load_audio_mp3(path):
    from scipy.io import wavfile
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
        print(f"   FFmpeg失败: {e}")
    return None, None

def save_audio_wav(audio, sample_rate, path):
    from scipy.io import wavfile
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(path, sample_rate, audio_int16)

async def generate_tts(text, output_path, voice=VOICE, speed=SPEED):
    try:
        import edge_tts
        rate_str = f"+{int((speed-1)*100)}%" if speed > 1 else f"{int((speed-1)*100)}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate_str)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"   Edge-TTS失败: {e}")
        return False

async def generate_one_news(seg):
    seg_id = seg["id"]
    text = seg["text"]
    year = seg["year"]
    out_wav = f"{seg_id}.wav"
    out_m4a = f"{seg_id}.m4a"
    out_path_wav = os.path.join(OUTPUT_DIR, out_wav)
    out_path_m4a = os.path.join(OUTPUT_DIR, out_m4a)
    pub_path_m4a = os.path.join(PUBLIC_DIR, out_m4a)

    if os.path.exists(pub_path_m4a) and os.path.getsize(pub_path_m4a) > 5000:
        return True
    if os.path.exists(out_path_m4a) and os.path.getsize(out_path_m4a) > 5000:
        shutil.copy2(out_path_m4a, pub_path_m4a)
        return True

    print(f"🎙️ {seg_id} ({year}年{seg.get('month','?')}月): {text[:35]}...")

    temp_dir = tempfile.gettempdir()
    tts_path = os.path.join(temp_dir, f"news_tts_{seg_id}.mp3")

    success = await generate_tts(text, tts_path)
    if not success:
        print(f"   ❌ TTS失败")
        return False

    sr, audio = load_audio_mp3(tts_path)
    if sr is None:
        return False

    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    audio = apply_vintage_50s(audio, sr)
    save_audio_wav(audio, sr, out_path_wav)

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        cmd = [ffmpeg_exe, '-y', '-i', out_path_wav, '-c:a', 'aac', '-b:a', '128k', '-ar', '24000', '-ac', '1', out_path_m4a]
        subprocess.run(cmd, capture_output=True)
        if os.path.exists(out_path_m4a):
            shutil.copy2(out_path_m4a, pub_path_m4a)
        else:
            shutil.copy2(out_path_wav, pub_path_m4a.replace('.m4a', '.wav'))
    except Exception as e:
        print(f"   m4a convert fail: {e}, fallback wav")
        shutil.copy2(out_path_wav, pub_path_m4a.replace('.m4a', '.wav'))

    dur = len(audio) / sr
    print(f"   ✅ {out_m4a} ({dur:.1f}秒)")

    try:
        if os.path.exists(tts_path):
            os.remove(tts_path)
    except:
        pass
    return True

async def main():
    print("=" * 60)
    print("时光调频 · 月度新闻TTS批量生成器 (1949-1960)")
    print("=" * 60)
    
    try:
        import edge_tts
    except ImportError:
        print("⚠️ 安装edge-tts中...")
        os.system(f"{sys.executable} -m pip install edge-tts -q")
        import edge_tts
    
    with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    news_list = data["news_briefs"]
    print(f"\n📰 待生成: {len(news_list)} 条月度新闻")
    print(f"📂 输出: {OUTPUT_DIR}")
    print()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    success = 0
    failed = 0
    
    # 分批生成，每批5个
    batch_size = 5
    for i in range(0, len(news_list), batch_size):
        batch = news_list[i:i+batch_size]
        tasks = [generate_one_news(seg) for seg in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r is True:
                success += 1
            else:
                failed += 1
    
    print(f"\n{'='*60}")
    print(f"✨ 完成！成功: {success}/{len(news_list)}, 失败: {failed}")

    print(f"\n📋 清理旧新闻文件并确认M4A就位...")
    old_wavs = [f for f in os.listdir(PUBLIC_DIR) if f.startswith("news_") and f.endswith(".wav")]
    for wf in old_wavs:
        try:
            os.remove(os.path.join(PUBLIC_DIR, wf))
        except:
            pass
    old_m4as_simple = [f for f in os.listdir(PUBLIC_DIR) if f.startswith("news_") and f.endswith(".m4a") and len(f.split("_")) == 3]
    for mf in old_m4as_simple:
        try:
            os.remove(os.path.join(PUBLIC_DIR, mf))
        except:
            pass

    copied = 0
    for seg in news_list:
        src = os.path.join(OUTPUT_DIR, f"{seg['id']}.m4a")
        dst = os.path.join(PUBLIC_DIR, f"{seg['id']}.m4a")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            copied += 1
        else:
            src_wav = os.path.join(OUTPUT_DIR, f"{seg['id']}.wav")
            if os.path.exists(src_wav):
                shutil.copy2(src_wav, dst.replace('.m4a', '.wav'))
                copied += 1
    print(f"✅ {copied} 个新闻文件已就位")

if __name__ == "__main__":
    asyncio.run(main())
