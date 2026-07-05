#!/usr/bin/env python3
"""
扫描生成的音频文件，输出前端可用的audio-pool.json配置
"""

import json
import os
import wave
import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool-scripts.json")
GENERATED_DIR = os.path.join(PROJECT_ROOT, "audio-lib", "pool-generated")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "audio-lib", "audio-pool.json")


def get_wav_duration(path):
    with wave.open(path, 'r') as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)


def year_to_pos(year):
    """年份(支持小数)映射到0-1位置"""
    return (year - 1950) / (1970 - 1950)


def main():
    with open(SCRIPTS_PATH, 'r', encoding='utf-8') as f:
        scripts = json.load(f)
    
    pool = {
        "version": "1.0",
        "sampleRate": 24000,
        "baseUrl": "/audio-lib/pool-generated/",
        "anchors": [],
        "floats": []
    }
    
    # 锚点电台
    for seg in scripts["anchor_events"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        pool["anchors"].append({
            "id": seg["id"],
            "type": "anchor",
            "title": seg["title"],
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": [0, 0.5, 1.0],
            "signalQuality": seg.get("signalQuality", 0.9),
            "volume": seg.get("volume", 0.9),
            "transitionSong": None
        })
    
    float_id = 0
    
    # 台呼ID
    for seg in scripts["station_ids"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        pool["floats"].append({
            "id": seg["id"],
            "type": "station_id",
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "positionSpread": 0.1,
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": [0],
            "signalQuality": 0.7,
            "volume": 0.7
        })
        float_id += 1
    
    # 新闻短句
    for seg in scripts["news_briefs"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        enter_points = [p / duration for p in seg["enterPoints"] if p < duration]
        pool["floats"].append({
            "id": seg["id"],
            "type": "news_brief",
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "positionSpread": 0.15,
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": enter_points if enter_points else [0],
            "signalQuality": 0.65,
            "volume": 0.75
        })
        float_id += 1
    
    # 生活片段
    for seg in scripts["life_snippets"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        pool["floats"].append({
            "id": seg["id"],
            "type": "life_snippet",
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "positionSpread": 0.12,
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": [0],
            "signalQuality": 0.6,
            "volume": 0.7
        })
        float_id += 1
    
    # 小栏目
    for seg in scripts["jingles"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        pool["floats"].append({
            "id": seg["id"],
            "type": "jingle",
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "positionSpread": 0.2,
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": [0],
            "signalQuality": 0.75,
            "volume": 0.8
        })
        float_id += 1
    
    # 歌曲片段
    for seg in scripts["song_clips"]:
        wav_path = os.path.join(GENERATED_DIR, f"{seg['id']}.wav")
        if not os.path.exists(wav_path):
            continue
        duration = get_wav_duration(wav_path)
        enter_points = [p / duration for p in seg["enterPoints"] if p < duration]
        pool["floats"].append({
            "id": seg["id"],
            "type": "song_clip",
            "title": seg["title"],
            "year": seg["year"],
            "position": year_to_pos(seg["year"]),
            "positionSpread": 0.25,
            "file": f"{seg['id']}.wav",
            "duration": round(duration, 2),
            "enterPoints": enter_points if enter_points else [0.2],
            "signalQuality": 0.8,
            "volume": 0.65
        })
        float_id += 1
    
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 配置文件已生成: {OUTPUT_PATH}")
    print(f"   锚点电台: {len(pool['anchors'])}")
    print(f"   浮动素材: {len(pool['floats'])}")
    print(f"   总计: {len(pool['anchors']) + len(pool['floats'])} 个音频文件")


if __name__ == "__main__":
    main()
