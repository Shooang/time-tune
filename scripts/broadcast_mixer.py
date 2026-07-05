#!/usr/bin/env python3
"""
时光调频 · 多轨音频合成引擎
============================
广播节目由多个音轨混合而成：
1. 人声轨（Voice）：TTS生成 → 年代感处理（带通/失真/电子管温暖感）
2. 底噪轨（Noise Bed）：粉红噪音贯穿始终，-40~-46dB
3. 背景音乐轨（BGM）：
   - 开场呼号（Opening Signature）：节目前奏
   - 间隔音乐（Bridge）：段落间过渡（人声停→音乐起→音乐弱→人声起）
   - 结束曲（Closing）：节目收尾

广播稿格式（支持音乐标记）：
  [OPENING_FANFARE]
  各位听众朋友们，晚上好。
  [BRIDGE]
  今天是一九五零年...
  [CLOSING]

年代预设（vintage preset）:
  50s: 频带300-3500Hz, 大失真, 强底噪, 语速+20%
  60s: 频带300-3800Hz, 中等失真, 较强底噪, 语速+18%
  70s: 频带250-4000Hz, 轻失真, 中等底噪, 语速+15%
  80s: 频带200-4500Hz, 微失真, 轻底噪, 语速+10%
"""

import os
import sys
import re
import json
import asyncio
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from typing import List, Tuple, Optional

# 导入收音机噪音模拟模块
sys.path.insert(0, str(Path(__file__).parent))
from radio_noise_sim import generate_vintage_radio_noise, fade as noise_fade

try:
    import edge_tts
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "edge-tts"], check=True)
    import edge_tts

# FFmpeg路径
FFMPEG = None
try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    result = subprocess.run(["which", "ffmpeg"], capture_output=True, text=True)
    if result.returncode == 0:
        FFMPEG = "ffmpeg"

# 路径配置
LIB_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib")
SR = 22050

# ============================================================================
# 年代预设参数
# ============================================================================
VINTAGE_PRESETS = {
    "50s": {
        "lowpass": 3500,
        "highpass": 300,
        "tube_drive": 0.8,
        "noise_gain_db": -30,       # 底噪（真实收音机噪音）
        "noise_crackle": 0.020,     # 静电爆裂声强度
        "noise_hum": 0.012,         # 50Hz交流嗡声强度
        "noise_hiss": 0.030,        # 高频嘶嘶声强度
        "noise_pink": 0.050,        # 粉红噪音基础
        "voice_rate": "+20%",
        "bass_boost": 3,
        "mid_boost": 2,
        "reverb_amount": 0.08,
        "opening_fanfare_gain_db": -8,
        "bridge_gain_db": -14,
        "bgm_gain_db": -28,
        "pause_between_segments": 0.8,
    },
    "60s": {
        "lowpass": 3800,
        "highpass": 280,
        "tube_drive": 0.5,
        "noise_gain_db": -32,
        "noise_crackle": 0.015,
        "noise_hum": 0.010,
        "noise_hiss": 0.025,
        "noise_pink": 0.045,
        "voice_rate": "+18%",
        "bass_boost": 2.5,
        "mid_boost": 1.5,
        "reverb_amount": 0.06,
        "opening_fanfare_gain_db": -10,
        "bridge_gain_db": -16,
        "bgm_gain_db": -30,
        "pause_between_segments": 0.7,
    },
    "70s": {
        "lowpass": 4000,
        "highpass": 250,
        "tube_drive": 0.3,
        "noise_gain_db": -34,       # 原-41，大幅提高到真实收音机水平
        "noise_crackle": 0.012,     # 静电爆裂
        "noise_hum": 0.008,         # 交流嗡声
        "noise_hiss": 0.020,        # 嘶嘶声
        "noise_pink": 0.040,        # 粉红底噪
        "voice_rate": "+15%",
        "bass_boost": 2,
        "mid_boost": 1,
        "reverb_amount": 0.05,
        "opening_fanfare_gain_db": -12,
        "bridge_gain_db": -18,
        "bgm_gain_db": -30,
        "pause_between_segments": 0.7,
    },
    "80s": {
        "lowpass": 4500,
        "highpass": 200,
        "tube_drive": 0.15,
        "noise_gain_db": -38,
        "noise_crackle": 0.006,
        "noise_hum": 0.005,
        "noise_hiss": 0.015,
        "noise_pink": 0.030,
        "voice_rate": "+10%",
        "bass_boost": 1,
        "mid_boost": 0.5,
        "reverb_amount": 0.03,
        "opening_fanfare_gain_db": -14,
        "bridge_gain_db": -20,
        "bgm_gain_db": -32,
        "pause_between_segments": 0.6,
    },
}

# 音色库（未来扩展）
VOICE_LIBRARY = {
    # 男声 - 新闻播报风格
    "yunxi": "zh-CN-YunxiNeural",       # 男声，新闻播报
    "yunyang": "zh-CN-YunyangNeural",   # 男声，新闻播报（用户认可）
    "yunjian": "zh-CN-YunjianNeural",   # 男声，正式风格
    "yunze": "zh-CN-YunzeNeural",       # 男声，沉稳
    # 女声
    "xiaoxiao": "zh-CN-XiaoxiaoNeural", # 女声，自然
    "xiaoyi": "zh-CN-XiaoyiNeural",     # 女声，温柔
    "xiaomo": "zh-CN-XiaomoNeural",     # 女声，知性
    "xiaoxuan": "zh-CN-XiaoxuanNeural", # 女声，新闻风格
    "xiaohong": "zh-CN-XiaohongNeural", # 女声
}

# ============================================================================
# 歌曲库（按年代分类，供Agent自动匹配）
# ============================================================================
SONGS_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/bgm/songs")

# 年代歌曲库：{年代: [(文件名, 歌名, 适用场景), ...]}
SONGS_LIBRARY = {
    "50s": [
        ("《歌唱祖国》1951年人民唱片第一版.mp3", "歌唱祖国", "开场/国庆"),
        ("《中国人民志愿军战歌》.mp3", "志愿军战歌", "抗美援朝/军事"),
        ("《抗美援朝进行曲》1950 年.mp3", "抗美援朝进行曲", "抗美援朝/军事"),
        ("《社会主义好》1957原版.mp3", "社会主义好", "经济建设/社会主义"),
        ("《三大纪律八项注意》1951 版.mp3", "三大纪律八项注意", "军事/解放军"),
        ("《南泥湾》郭兰英-1960 年代.mp3", "南泥湾", "大生产/农业"),
    ],
    "60s": [
        ("《我们走在大路上》1963原版.mp3", "我们走在大路上", "经济建设/社会主义"),
        ("《十送红军》1963版 原唱.mp3", "十送红军", "红军/革命"),
        ("《大海航行靠舵手》1965原版 原唱贾世骏.mp3", "大海航行靠舵手", "毛泽东思想/开场"),
        ("《东方红》1965原版.mp3", "东方红", "开场/毛泽东"),
        ("《南泥湾》郭兰英-1960 年代.mp3", "南泥湾", "大生产/农业"),
        ("《珊瑚颂》1961 -电影《红珊瑚》插曲.mp3", "珊瑚颂", "文艺/电影"),
        ("《一代一代往下传》1966.mp3", "一代一代往下传", "革命传承"),
    ],
    "70s": [
        ("《北京颂歌》1974年 李双江 原版.mp3", "北京颂歌", "开场/首都"),
        ("《咱是生产队的半边天》刘桂琴 1970年代.mp3", "咱是生产队的半边天", "农业/生产队"),
        ("《祝酒歌》李光羲.mp3", "祝酒歌", "庆祝/喜悦"),
        ("《太阳最红，毛主席最亲》1976年原版.mp3", "太阳最红毛主席最亲", "毛泽东/缅怀"),
        ("《大海航行靠舵手》1965原版 原唱贾世骏.mp3", "大海航行靠舵手", "毛泽东思想/过渡"),
        ("《东方红》1965原版.mp3", "东方红", "开场/卫星"),
        ("《社会主义好》.mp3", "社会主义好", "经济建设"),
    ],
    "80s": [
        ("《在希望的田野上》原版.mp3", "在希望的田野上", "改革开放/农村"),
        ("《年轻的朋友来相会》 原版.mp3", "年轻的朋友来相会", "改革开放/青春"),
        ("《乡恋》李谷一 《三峡传说》原声.mp3", "乡恋", "文艺/抒情"),
    ],
}

# 纯音乐伴奏库（无人声，用于开场/间奏/背景音乐）
INSTRUMENTAL_LIBRARY = [
    "《歌唱祖国 》伴奏 纯音乐.mp3",
    "《没有共产党就没有新中国》伴奏纯音乐.mp3",
    "《大帅练兵歌》 纯音乐.mp3",
]

# 事件关键词 → 歌曲匹配规则（供Agent参考）
EVENT_SONG_MATCHING = {
    "卫星|东方红|航天|太空": ("《东方红》1965原版.mp3", "卫星发射与东方红相关"),
    "抗美援朝|志愿军|鸭绿江": ("《中国人民志愿军战歌》.mp3", "抗美援朝相关"),
    "大生产|南泥湾|开荒|农业": ("《南泥湾》郭兰英-1960 年代.mp3", "大生产运动"),
    "生产队|半边天|妇女": ("《咱是生产队的半边天》刘桂琴 1970年代.mp3", "生产队/妇女"),
    "北京|首都|天安门": ("《北京颂歌》1974年 李双江 原版.mp3", "首都北京"),
    "庆祝|胜利|捷报|欢呼": ("《祝酒歌》李光羲.mp3", "庆祝胜利"),
    "改革开放|田野|希望": ("《在希望的田野上》原版.mp3", "改革开放"),
    "毛泽东|毛主席": ("《太阳最红，毛主席最亲》1976年原版.mp3", "毛主席"),
    "社会主义|建设": ("《社会主义好》.mp3", "社会主义建设"),
    "走在大路上|经济": ("《我们走在大路上》1963原版.mp3", "经济建设"),
}


# ============================================================================
# 音频处理工具函数
# ============================================================================
def load_audio(path: Path, target_sr: int = SR) -> np.ndarray:
    """加载音频为单声道numpy数组（支持wav/mp3/aiff等）"""
    path = Path(path)
    # 如果不是wav，先用FFmpeg转换
    if path.suffix.lower() not in ['.wav']:
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmpf:
            tmpwav = Path(tmpf.name)
        cmd = [
            FFMPEG, "-y", "-i", str(path),
            "-ac", "1", "-ar", str(target_sr),
            "-acodec", "pcm_s16le",
            str(tmpwav)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            try: tmpwav.unlink()
            except: pass
            raise ValueError(f"无法加载音频: {path}")
        sr, data = wavfile.read(str(tmpwav))
        try: tmpwav.unlink()
        except: pass
    else:
        sr, data = wavfile.read(str(path))
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    if len(data.shape) > 1:
        data = data.mean(axis=1)
    if sr != target_sr:
        # 简单重采样
        ratio = target_sr / sr
        n_samples = int(len(data) * ratio)
        indices = np.linspace(0, len(data)-1, n_samples)
        data = np.interp(indices, np.arange(len(data)), data)
    return data.astype(np.float32)


def save_audio(audio: np.ndarray, path: Path, sr: int = SR):
    """保存为16位WAV"""
    audio = np.clip(audio, -1.0, 1.0)
    audio_int = (audio * 32767).astype(np.int16)
    wavfile.write(str(path), sr, audio_int)


def db_to_linear(db: float) -> float:
    return 10.0 ** (db / 20.0)


def apply_tube_warmth(audio: np.ndarray, drive: float = 1.5) -> np.ndarray:
    """模拟电子管温暖感（软削波失真）"""
    if drive <= 0:
        return audio
    # 电子管失真：tanh软削波 + 偶次谐波
    driven = audio * drive
    warm = np.tanh(driven)
    # 加入少量偶次谐波增强温暖感
    warm += 0.15 * np.tanh(driven * 2)
    # 归一化
    warm = warm / (np.max(np.abs(warm)) + 1e-8) * np.max(np.abs(audio))
    return warm


def apply_reverb(audio: np.ndarray, amount: float = 0.05, sr: int = SR) -> np.ndarray:
    """简单混响（模拟收音机箱体/房间感）"""
    if amount <= 0:
        return audio
    # 多延迟反馈
    delays = [0.03, 0.07, 0.11, 0.17]
    decays = [0.4, 0.3, 0.2, 0.15]
    out = audio.copy()
    for delay_sec, decay in zip(delays, decays):
        delay_samples = int(delay_sec * sr)
        if delay_samples < len(out):
            out[delay_samples:] += audio[:-delay_samples] * decay * amount
    out = out / (1 + amount * 2)
    return out


def ffmpeg_vintage_process(input_path: Path, output_path: Path, preset: dict):
    """使用FFmpeg对TTS人声应用年代感处理"""
    lp = preset["lowpass"]
    hp = preset["highpass"]
    bass = preset["bass_boost"]
    mid = preset["mid_boost"]

    # 简化滤镜链（兼容更多FFmpeg版本）
    # 高通→低通→均衡→压缩
    filter_chain = (
        f"highpass=f={hp},lowpass=f={lp},"
        f"equalizer=f=400:t=q:w=1:g={bass},"
        f"equalizer=f=1200:t=q:w=1.5:g={mid},"
        f"acompressor=threshold=-18dB:ratio=4:attack=3:release=80:makeup=2"
    )

    cmd = [
        FFMPEG, "-y", "-i", str(input_path),
        "-af", filter_chain,
        "-ac", "1", "-ar", str(SR),
        "-acodec", "pcm_s16le",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        # 如果复杂滤镜失败，尝试基本处理
        print(f"  ⚠️ FFmpeg处理失败，尝试基础处理...")
        simple_filter = f"highpass=f={hp},lowpass=f={lp},acompressor=threshold=-18dB:ratio=4"
        cmd = [
            FFMPEG, "-y", "-i", str(input_path),
            "-af", simple_filter,
            "-ac", "1", "-ar", str(SR),
            "-acodec", "pcm_s16le",
            str(output_path)
        ]
        result2 = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result2.returncode != 0:
            # 最后兜底：直接转换格式
            cmd = [
                FFMPEG, "-y", "-i", str(input_path),
                "-ac", "1", "-ar", str(SR),
                "-acodec", "pcm_s16le",
                str(output_path)
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def generate_pink_noise(duration_sec: float, sr: int = SR) -> np.ndarray:
    """生成粉红噪音（基础噪音层）"""
    n = int(duration_sec * sr)
    n_octaves = 16
    octaves = np.random.randn(n_octaves, n)
    for i in range(n_octaves):
        k = 2 ** (i + 1)
        kernel = np.ones(k) / k
        octaves[i] = np.convolve(octaves[i], kernel, mode='same')
    pink = np.sum(octaves, axis=0)
    pink = pink / (np.max(np.abs(pink)) + 1e-8) * 0.3
    return pink.astype(np.float32)


def generate_radio_noise(duration_sec: float, sr: int = SR,
                         crackle_amount: float = 0.015,
                         hum_amount: float = 0.008,
                         hiss_amount: float = 0.025,
                         pink_amount: float = 0.04) -> np.ndarray:
    """
    生成真实老旧收音机噪音（多层合成）：
    1. 粉红噪音：基础底噪（收音机热噪音）
    2. 嘶嘶声(hiss)：高频白噪音（电子管/电路高频噪音）
    3. 50Hz交流嗡声(hum)：电源干扰（含二次谐波）
    4. 静电爆裂声(crackle)：随机噼啪声（调幅收音机大气干扰/静电）
    """
    n = int(duration_sec * sr)
    t = np.arange(n) / sr
    noise = np.zeros(n, dtype=np.float32)

    # 1. 粉红噪音基础层
    if pink_amount > 0:
        pink = generate_pink_noise(duration_sec, sr)
        noise += pink * pink_amount

    # 2. 高频嘶嘶声（带通白噪音，模拟电子管高频噪音）
    if hiss_amount > 0:
        hiss = np.random.randn(n).astype(np.float32)
        # 高通滤波，保留高频
        hiss = np.convolve(hiss, np.array([1, -0.98]), mode='same')
        noise += hiss * hiss_amount

    # 3. 50Hz交流嗡声 + 二次谐波（100Hz）
    if hum_amount > 0:
        hum = np.sin(2 * np.pi * 50 * t) * 0.6 + np.sin(2 * np.pi * 100 * t) * 0.3
        hum += np.sin(2 * np.pi * 150 * t) * 0.1  # 三次谐波更弱
        # 随机调制（模拟交流声不稳定）
        hum_mod = 0.8 + 0.4 * np.random.randn(n).astype(np.float32)
        hum_mod = np.clip(hum_mod, 0.5, 1.5)
        noise += hum.astype(np.float32) * hum_amount * hum_mod

    # 4. 静电爆裂声（随机短脉冲，模拟调幅收音机静电）
    if crackle_amount > 0:
        # 随机生成爆裂点（每秒约3-8个）
        num_crackles = int(duration_sec * np.random.uniform(3, 8))
        crackle_indices = np.random.randint(0, n - int(sr * 0.005), num_crackles)
        for idx in crackle_indices:
            # 爆裂声是一个短的衰减脉冲
            dur = np.random.randint(int(sr * 0.001), int(sr * 0.005))
            envelope = np.exp(-np.linspace(0, 10, dur))
            # 爆裂的内容是宽带噪音
            crack = np.random.randn(dur).astype(np.float32) * envelope
            # 随机幅度
            amp = np.random.uniform(0.3, 1.0) * crackle_amount * 5
            if idx + dur < n:
                noise[idx:idx+dur] += crack * amp

    return noise.astype(np.float32)


# ============================================================================
# TTS 生成（支持 Edge-TTS 和 macOS say 命令备选）
# ============================================================================
def generate_tts_say(text: str, voice: str, rate: str, output_path: Path) -> bool:
    """使用macOS自带say命令作为备选TTS（用于测试）"""
    # macOS say中文音色映射
    say_voice_map = {
        "zh-CN-YunxiNeural": "Eddy (中文（中国大陆）)",
        "zh-CN-YunyangNeural": "Reed (中文（中国大陆）)",
        "zh-CN-YunjianNeural": "Rocko (中文（中国大陆）)",
        "zh-CN-YunzeNeural": "Grandpa (中文（中国大陆）)",
        "zh-CN-XiaoxiaoNeural": "Tingting (中文（中国大陆）)",
        "zh-CN-XiaoyiNeural": "Sandy (中文（中国大陆）)",
        "zh-CN-XiaomoNeural": "Shelley (中文（中国大陆）)",
        "zh-CN-XiaoxuanNeural": "Flo (中文（中国大陆）)",
        "zh-CN-XiaohongNeural": "Grandma (中文（中国大陆）)",
    }
    say_voice = say_voice_map.get(voice, "Tingting (中文（中国大陆）)")

    # 语速：Edge-TTS rate="+20%" 对应 say rate 大约 220-240 wpm
    # say默认是175 wpm左右
    rate_wpm = 220
    if "+20%" in rate:
        rate_wpm = 240
    elif "+15%" in rate:
        rate_wpm = 225
    elif "+10%" in rate:
        rate_wpm = 210
    elif "+25%" in rate:
        rate_wpm = 250

    aiff_path = output_path.with_suffix(".aiff")
    cmd = [
        "say", "-v", say_voice, "-r", str(rate_wpm),
        "-o", str(aiff_path), text
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"  ⚠️ say命令失败: {result.stderr}")
        return False

    # 转换为mp3
    cmd = [
        FFMPEG, "-y", "-i", str(aiff_path),
        "-acodec", "libmp3lame", "-b:a", "128k",
        str(output_path)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        aiff_path.unlink()
    except:
        pass
    return result.returncode == 0


async def generate_tts_segment(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    use_fallback: bool = True,
    max_retries: int = 3
) -> bool:
    """生成单段TTS语音，先尝试Edge-TTS，失败则回退到say命令"""
    import asyncio
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(output_path))
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0)  # 等待1秒后重试
                continue
            if use_fallback:
                print(f"  ℹ️ Edge-TTS不可用({type(e).__name__})，使用macOS say备选...")
                return generate_tts_say(text, voice, rate, output_path)
            print(f"  ⚠️ TTS生成失败: {e}")
            return False
    return False


# ============================================================================
# 广播稿解析
# ============================================================================
def parse_script(script_text: str) -> List[dict]:
    """
    解析广播稿，返回段落列表。
    每个段落是:
      {"type": "text", "content": "..."}
      {"type": "marker", "name": "OPENING_FANFARE"|"BRIDGE"|"CLOSING"|"SONG", "duration_sec": N}
    """
    segments = []
    # 匹配标记 [XXX] 或 [XXX:duration]
    pattern = r'\[(OPENING_FANFARE|BRIDGE|CLOSING|SONG)(?::(\d+(?:\.\d+)?))?\]'

    pos = 0
    for match in re.finditer(pattern, script_text):
        # 标记前的文本
        text_before = script_text[pos:match.start()].strip()
        if text_before:
            segments.append({"type": "text", "content": text_before})

        # 标记本身
        marker_name = match.group(1)
        duration = float(match.group(2)) if match.group(2) else None
        segments.append({"type": "marker", "name": marker_name, "duration_sec": duration})

        pos = match.end()

    # 剩余文本
    remaining = script_text[pos:].strip()
    if remaining:
        segments.append({"type": "text", "content": remaining})

    return segments


# ============================================================================
# 多轨混合
# ============================================================================
def mix_tracks(timeline: List[Tuple[float, np.ndarray, float]], total_duration: float, sr: int = SR) -> np.ndarray:
    """
    将多个音频片段按时间轴混合。
    timeline: [(start_time_sec, audio_data, gain_db), ...]
    """
    n_samples = int(total_duration * sr)
    mix = np.zeros(n_samples, dtype=np.float32)

    for start_sec, audio, gain_db in timeline:
        start_sample = int(start_sec * sr)
        gain = db_to_linear(gain_db)
        end_sample = min(start_sample + len(audio), n_samples)
        chunk_len = end_sample - start_sample
        if chunk_len <= 0:
            continue
        mix[start_sample:end_sample] += audio[:chunk_len] * gain

    # 限制幅度
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix / peak * 0.9
    return mix


def fade(audio: np.ndarray, fade_in_sec: float = 0.5, fade_out_sec: float = 0.5, sr: int = SR) -> np.ndarray:
    """添加淡入淡出"""
    out = audio.copy()
    fi = int(fade_in_sec * sr)
    fo = int(fade_out_sec * sr)
    if fi > 0 and fi < len(out):
        out[:fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < len(out):
        out[-fo:] *= np.linspace(1, 0, fo)
    return out


def crossfade(audio: np.ndarray, fade_in_sec: float = 0, fade_out_sec: float = 0, sr: int = SR) -> np.ndarray:
    """自定义淡入淡出"""
    return fade(audio, fade_in_sec, fade_out_sec, sr)


# ============================================================================
# 主合成函数
# ============================================================================
async def synthesize_broadcast(
    script: str,
    output_path: Path,
    preset_name: str = "70s",
    voice_key: str = "yunxi",
    lib_dir: Path = LIB_DIR
):
    """
    合成完整广播节目。
    """
    preset = VINTAGE_PRESETS.get(preset_name, VINTAGE_PRESETS["70s"])
    voice_name = VOICE_LIBRARY.get(voice_key, VOICE_LIBRARY["yunxi"])

    print(f"\n{'='*60}")
    print(f"📻 时光调频 · 多轨音频合成")
    print(f"{'='*60}")
    print(f"  年代预设: {preset_name}")
    print(f"  播音员音色: {voice_name}")
    print(f"  语速: {preset['voice_rate']}")
    print(f"  底噪音量: {preset['noise_gain_db']}dB")
    print(f"{'='*60}\n")

    # 解析广播稿
    segments = parse_script(script)
    print(f"📝 解析广播稿: {len(segments)} 个段落")

    # ---- 音乐素材加载 ----
    # 使用歌曲库中的纯音乐伴奏做开场/间奏/背景音乐
    # 使用真实年代歌曲做结尾

    songs_dir = SONGS_DIR

    # 开场：用纯音乐伴奏（无人声）
    instrumental_path = None
    for inst_name in INSTRUMENTAL_LIBRARY:
        p = songs_dir / inst_name
        if p.exists():
            instrumental_path = p
            break
    if instrumental_path:
        fanfare_path = instrumental_path
        print(f"  🎺 开场曲: 纯音乐伴奏 ({instrumental_path.name})")
    else:
        # 回退：用年代歌曲的前奏部分
        era_songs = SONGS_LIBRARY.get(preset_name, SONGS_LIBRARY["70s"])
        if era_songs:
            fanfare_path = songs_dir / era_songs[0][0]
            print(f"  🎺 开场曲: 年代歌曲前奏 ({era_songs[0][1]})")
        else:
            fanfare_path = None
            print(f"  ⚠️ 无可用开场音乐")

    # 间隔音乐：用纯音乐伴奏（与人声播报时使用的背景音乐相同）
    bridge_path = instrumental_path

    # 结尾歌曲：根据广播稿内容自动匹配年代歌曲
    # 扫描广播稿中的关键词，匹配最合适的歌曲
    song_path = None
    song_name = "未匹配"
    script_text_full = script  # 全文用于关键词匹配

    # 先检查广播稿中是否有[SONG:文件名]指定
    song_match = re.search(r'\[SONG:([^\]]+)\]', script)
    if song_match:
        specified_song = song_match.group(1).strip()
        # 在songs目录中查找匹配文件
        for f in songs_dir.glob("*.mp3"):
            if specified_song in f.name or f.name in specified_song:
                song_path = f
                song_name = f.stem
                break

    # 如果没有指定，自动匹配
    if song_path is None:
        best_match = None
        best_score = 0
        era_songs = SONGS_LIBRARY.get(preset_name, [])
        for pattern, (song_file, reason) in EVENT_SONG_MATCHING.items():
            keywords = pattern.split("|")
            score = sum(1 for kw in keywords if kw in script_text_full)
            if score > best_score:
                best_score = score
                # 确认歌曲在当前年代库中
                for sf, sn, sc in era_songs:
                    if sf == song_file:
                        best_match = (songs_dir / song_file, sn, reason)
                        break

        if best_match:
            song_path, song_name, match_reason = best_match
            print(f"  🎵 结尾歌曲: 《{song_name}》（匹配: {match_reason}）")
        else:
            # 默认：用当前年代第一首歌曲
            if era_songs:
                song_path = songs_dir / era_songs[0][0]
                song_name = era_songs[0][1]
                print(f"  🎵 结尾歌曲: 《{song_name}》（年代默认）")
            else:
                print(f"  ⚠️ 未找到匹配歌曲")

    # 加载音频
    fanfare_audio = load_audio(fanfare_path) if fanfare_path and fanfare_path.exists() else None
    bridge_audio = fanfare_audio  # 间奏与开场用同一个纯音乐
    song_audio = load_audio(song_path) if song_path and song_path.exists() else None
    # 结尾过渡用纯音乐
    ending_audio = fanfare_audio

    has_fanfare = fanfare_audio is not None and len(fanfare_audio) > 0
    has_bridge = bridge_audio is not None and len(bridge_audio) > 0
    has_song = song_audio is not None and len(song_audio) > 0
    if not has_fanfare:
        print("⚠️ 开场音乐缺失，将仅使用人声开场")

    # 临时工作目录
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)

        # ---- 第一步：生成所有人声片段 ----
        print("\n🗣️ 生成TTS人声音频...")
        voice_segments = []  # [(start_sec, audio_data), ...]
        tts_raw = tmp / "tts_raw"
        tts_raw.mkdir()
        tts_processed = tmp / "tts_processed"
        tts_processed.mkdir()

        text_idx = 0
        timeline_events = []  # 用于构建时间轴

        current_time = 0.0

        for seg_idx, seg in enumerate(segments):
            if seg["type"] == "marker":
                marker_name = seg["name"]
                marker_dur = seg["duration_sec"]

                if marker_name == "OPENING_FANFARE" and has_fanfare:
                    dur = marker_dur or min(10.0, len(fanfare_audio)/SR - 0.5)
                    fanfare_play = fanfare_audio[:int(dur*SR)]
                    fanfare_play = fade(fanfare_play, 0.5, 2.0)
                    timeline_events.append({
                        "type": "audio",
                        "start": current_time,
                        "data": fanfare_play,
                        "gain_db": preset["opening_fanfare_gain_db"]
                    })
                    print(f"  🎺 开场音乐: {current_time:.1f}s - {current_time+dur:.1f}s")
                    current_time += dur - 2.0  # 音乐淡出时人声开始（重叠2秒）

                elif marker_name == "BRIDGE" and has_bridge:
                    dur = marker_dur or 7.0
                    # 间奏用纯音乐
                    bridge_play = fanfare_audio[:int(dur*SR)] if has_fanfare else np.zeros(int(dur*SR))
                    bridge_play = fade(bridge_play, 0.5, 1.5)
                    timeline_events.append({
                        "type": "audio",
                        "start": current_time - 0.3,
                        "data": bridge_play,
                        "gain_db": preset["bridge_gain_db"]
                    })
                    print(f"  🔔 间隔音乐: {current_time:.1f}s - {current_time+dur:.1f}s")
                    current_time += dur - 1.5

                elif marker_name == "CLOSING" and has_fanfare:
                    # 结尾过渡：纯音乐淡出
                    closing_dur = marker_dur or 5.0
                    closing = fanfare_audio[:int(closing_dur*SR)]
                    closing = fade(closing, 0.5, 2.5)
                    timeline_events.append({
                        "type": "audio",
                        "start": current_time,
                        "data": closing,
                        "gain_db": preset["opening_fanfare_gain_db"] - 2
                    })
                    print(f"  🎶 结尾过渡: {current_time:.1f}s - {current_time+closing_dur:.1f}s")
                    current_time += closing_dur

                elif marker_name == "SONG" and has_song:
                    # 播放真实年代歌曲
                    song_dur = marker_dur or min(30.0, len(song_audio)/SR)
                    song_play = song_audio[:int(song_dur*SR)]
                    song_play = fade(song_play, 1.0, 4.0)
                    timeline_events.append({
                        "type": "audio",
                        "start": current_time,
                        "data": song_play,
                        "gain_db": preset["opening_fanfare_gain_db"] - 3
                    })
                    print(f"  🎵 结尾歌曲《{song_name}》: {current_time:.1f}s - {current_time+song_dur:.1f}s")
                    current_time += song_dur

            elif seg["type"] == "text":
                text = seg["content"]
                if not text:
                    continue
                # 清理文本：将换行符替换为空格/停顿，多余空格合并
                text = text.replace('\n', '，').replace('。，', '。')
                text = re.sub(r'\s+', ' ', text).strip()

                # 生成TTS
                raw_path = tts_raw / f"voice_{text_idx:03d}.mp3"
                processed_path = tts_processed / f"voice_{text_idx:03d}.wav"

                print(f"  🎤 段落 {text_idx+1}: \"{text[:20]}...\"")
                success = await generate_tts_segment(text, voice_name, preset["voice_rate"], raw_path)

                if success and raw_path.exists():
                    # 应用FFmpeg年代处理
                    ffmpeg_vintage_process(raw_path, processed_path, preset)

                    # 加载音频（优先处理后WAV，失败则用原始MP3）
                    voice_audio = None
                    load_errors = []
                    if processed_path.exists() and processed_path.stat().st_size > 1000:
                        try:
                            voice_audio = load_audio(processed_path)
                        except Exception as e:
                            load_errors.append(f"wav失败:{e}")

                    if voice_audio is None:
                        try:
                            voice_audio = load_audio(raw_path)
                        except Exception as e:
                            load_errors.append(f"mp3失败:{e}")

                    if voice_audio is not None and len(voice_audio) > 0:
                        # 应用电子管温暖感
                        voice_audio = apply_tube_warmth(voice_audio, preset["tube_drive"])

                        # 应用轻微混响
                        voice_audio = apply_reverb(voice_audio, preset["reverb_amount"])

                        # 段首淡入，段尾淡出（避免硬切）
                        voice_audio = fade(voice_audio, 0.05, 0.1)

                        # 加入人声时间轴
                        timeline_events.append({
                            "type": "audio",
                            "start": current_time,
                            "data": voice_audio,
                            "gain_db": -1
                        })

                        seg_dur = len(voice_audio) / SR
                        print(f"     时长: {seg_dur:.1f}s, 结束于: {current_time+seg_dur:.1f}s")

                        # 添加背景音乐（人声播放时，纯音乐在低音量伴奏）
                        if has_fanfare:
                            bgm_start = int(current_time * SR)
                            bgm_dur = seg_dur + 1.0  # 比人声多1秒
                            bgm_seg = fanfare_audio[bgm_start % len(fanfare_audio):]
                            # 如果不够长，循环补齐
                            if len(bgm_seg) < int(bgm_dur * SR):
                                repeats = int(np.ceil(bgm_dur * SR / len(fanfare_audio)))
                                bgm_seg = np.tile(fanfare_audio, repeats)
                            bgm_seg = bgm_seg[:int(bgm_dur * SR)]
                            bgm_seg = fade(bgm_seg, 0.5, 1.0)
                            timeline_events.append({
                                "type": "audio",
                                "start": current_time,
                                "data": bgm_seg,
                                "gain_db": preset["bgm_gain_db"]
                            })

                        current_time += seg_dur + preset["pause_between_segments"]
                    else:
                        print(f"     ⚠️ 无法加载音频，跳过此段落")

                text_idx += 1

        # ---- 第二步：添加底噪轨（老式收音机真实噪音）----
        total_duration = current_time + 3.0  # 最后留3秒
        print(f"\n🔊 混合音轨... 总时长: {total_duration:.1f}秒")

        # 使用收音机噪音模拟模块生成真实底噪
        noise = generate_vintage_radio_noise(total_duration, preset_name, SR)
        # 开场前1秒底噪渐入，结尾2秒渐出
        noise = noise_fade(noise, 1.0, 2.0, SR)
        # 底噪整体音量（再提高10%：-34→约-33dB，即增益1.12x）
        noise_gain = db_to_linear(preset["noise_gain_db"] + 1)  # +1dB ≈ 10%
        timeline_events.append({
            "type": "audio",
            "start": 0,
            "data": noise,
            "gain_db": preset["noise_gain_db"] + 1  # 底噪+1dB（约10%）
        })

        # ---- 第三步：混合所有音轨 ----
        mix = np.zeros(int(total_duration * SR), dtype=np.float32)
        for event in timeline_events:
            start_sample = int(event["start"] * SR)
            gain = db_to_linear(event["gain_db"])
            audio = event["data"]
            end_sample = min(start_sample + len(audio), len(mix))
            chunk_len = end_sample - start_sample
            if chunk_len > 0:
                mix[start_sample:end_sample] += audio[:chunk_len] * gain

        # 全局标准化
        peak = np.max(np.abs(mix))
        if peak > 0.9:
            mix = mix / peak * 0.85

        # 最终应用轻微带通滤波（全频带）
        save_audio(mix, tmp / "final_mix.wav")

        # 用FFmpeg做最终母带处理（全频带限制+轻微饱和）
        cmd = [
            FFMPEG, "-y", "-i", str(tmp / "final_mix.wav"),
            "-af", f"alimiter=limit=0.9,lowpass=f={preset['lowpass']+500}",
            "-ac", "1", "-ar", "44100",
            "-codec:a", "libmp3lame", "-b:a", "128k",
            str(output_path)
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)

        print(f"\n✅ 合成完成！输出文件: {output_path}")
        print(f"   总时长: {total_duration:.1f}秒")

        # 输出摘要
        stats = {
            "preset": preset_name,
            "voice": voice_name,
            "duration_sec": round(total_duration, 1),
            "num_segments": text_idx,
            "params": preset
        }
        print(f"\n📊 合成参数:")
        print(f"   人声TTS: {voice_name} @ {preset['voice_rate']}")
        print(f"   频带: {preset['highpass']}Hz - {preset['lowpass']}Hz")
        print(f"   电子管驱动: {preset['tube_drive']}x")
        print(f"   底噪: {preset['noise_gain_db']}dB")
        print(f"   混响: {preset['reverb_amount']*100:.0f}%")

        return stats


# ============================================================================
# CLI 入口
# ============================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="时光调频 · 多轨广播音频合成")
    parser.add_argument("-s", "--script", type=str, help="广播稿文本文件路径")
    parser.add_argument("-o", "--output", type=str, default="output/broadcast_test.mp3")
    parser.add_argument("-p", "--preset", type=str, default="70s",
                        choices=list(VINTAGE_PRESETS.keys()))
    parser.add_argument("-v", "--voice", type=str, default="yunxi",
                        choices=list(VOICE_LIBRARY.keys()))
    parser.add_argument("-t", "--text", type=str, help="直接传入广播稿文本")
    args = parser.parse_args()

    if args.text:
        script_text = args.text
    elif args.script:
        script_text = Path(args.script).read_text(encoding='utf-8')
    else:
        # 默认测试脚本
        script_text = """[OPENING_FANFARE]
中央人民广播电台。中央人民广播电台。
各位听众朋友们，晚上好。
今天是一九七零年，欢迎收听全国新闻联播节目。
[BRIDGE]
首先报告国内要闻。
我国第一颗人造地球卫星东方红一号发射成功以来，全国人民欢欣鼓舞，各地纷纷举行庆祝活动。
在工农业生产战线上，广大工人和贫下中农同志，抓革命，促生产，取得了优异成绩。
[BRIDGE]
下面报告国际新闻。
世界人民反对帝国主义的斗争不断高涨。
[CLOSING]
各位听众，这次全国新闻联播节目播送完了，感谢收听，再会。"""

    output_path = Path("/Users/swan/Documents/1024/vibe/时光收音机") / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    asyncio.run(synthesize_broadcast(
        script_text, output_path,
        preset_name=args.preset,
        voice_key=args.voice
    ))


if __name__ == "__main__":
    main()
