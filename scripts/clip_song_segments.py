#!/usr/bin/env python3
"""
时光调频 · 歌曲副歌片段剪辑器

从完整歌曲文件中剪辑副歌片段，用于音频池。
"""

import json
import os
import subprocess
import numpy as np
from scipy.io import wavfile

import imageio_ffmpeg

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool-scripts.json")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "pool-generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_audio_any(path, target_sr=24000):
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    wav_path = path + '_temp_clip.wav'
    cmd = [ffmpeg_exe, '-y', '-i', path, '-ar', str(target_sr), '-ac', '1', wav_path]
    subprocess.run(cmd, capture_output=True)
    if os.path.exists(wav_path):
        sr, audio = wavfile.read(wav_path)
        os.remove(wav_path)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        return sr, audio.astype(np.float32) / 32768.0
    return None, None


def save_audio_wav(audio, sample_rate, path):
    audio_int16 = (audio * 32767).astype(np.int16)
    wavfile.write(path, sample_rate, audio_int16)


def apply_vintage_music_effect(audio, sample_rate, year):
    from scipy.signal import butter, lfilter
    
    if year < 1955:
        lowcut, highcut = 300, 3500
        noise_level = 0.008
    elif year < 1965:
        lowcut, highcut = 320, 3800
        noise_level = 0.006
    else:
        lowcut, highcut = 350, 4200
        noise_level = 0.004
    
    nyq = 0.5 * sample_rate
    b, a = butter(4, [lowcut/nyq, highcut/nyq], btype='band')
    audio = lfilter(b, a, audio)
    
    white = np.random.randn(len(audio)).astype(np.float32) * noise_level
    audio = audio * 0.92 + white
    
    fade_len = int(sample_rate * 0.1)
    audio[:fade_len] *= np.linspace(0, 1, fade_len)
    audio[-fade_len:] *= np.linspace(1, 0, fade_len)
    
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.85
    
    return audio


def main():
    print("=" * 60)
    print("时光调频 · 歌曲副歌片段剪辑器")
    print("=" * 60)
    
    with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
        pool = json.load(f)
    
    success = 0
    
    for song in pool["song_clips"]:
        song_id = song["id"]
        title = song["title"]
        src_path = os.path.join(PROJECT_ROOT, song["file"])
        clip_start = song["clipStart"]
        clip_duration = song["clipDuration"]
        year = song["year"]
        
        print(f"\n🎵 剪辑 {song_id}: {title}")
        
        if not os.path.exists(src_path):
            print(f"   ❌ 文件不存在: {src_path}")
            continue
        
        print(f"   读取: {src_path}")
        sr, audio = load_audio_any(src_path)
        if audio is None:
            print(f"   ❌ 加载失败")
            continue
        
        total_dur = len(audio) / sr
        print(f"   总时长: {total_dur:.1f}秒, 目标: {clip_start}s - {clip_start+clip_duration}s")
        
        start_sample = int(clip_start * sr)
        end_sample = int((clip_start + clip_duration) * sr)
        end_sample = min(end_sample, len(audio))
        
        if start_sample >= len(audio):
            start_sample = max(0, len(audio) // 3)
            end_sample = min(start_sample + int(clip_duration * sr), len(audio))
        
        clip = audio[start_sample:end_sample]
        
        print(f"   应用年代感处理...")
        clip = apply_vintage_music_effect(clip, sr, year)
        
        out_path = os.path.join(OUTPUT_DIR, f"{song_id}.wav")
        save_audio_wav(clip, sr, out_path)
        print(f"   ✅ 保存: {out_path} ({len(clip)/sr:.1f}秒)")
        success += 1
    
    print(f"\n{'='*60}")
    print(f"✨ 完成！成功剪辑: {success}/{len(pool['song_clips'])}")
    print(f"📂 输出目录: {OUTPUT_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
