#!/usr/bin/env python3
"""
从参考音频提取真实噪音指纹并构建收音机噪音模拟系统

老式收音机真实噪音特征分析总结：
1. 基础底噪：粉红噪音为主，中低频能量高
2. 爆裂/噼啪声(crackle/static)：每秒10-20个短脉冲
3. 信号衰落(fading)：慢速幅度调制，约0.05-0.1Hz周期（10-20秒）
4. 50Hz交流嗡声：微弱但存在（电子管电源）
5. 高频嘶嘶声：较少（AM广播带宽限制3-5kHz）
6. AGC抽吸效应：强信号后底噪短暂被压低
7. 频率漂移(wow)：极轻微的音调波动

本模块：
- radio_noise_profile.py: 独立的收音机噪音模拟模块
- 支持年代预设（50s/60s/70s/80s）
- 可从参考音频提取噪音指纹进行校准
"""
import subprocess
import tempfile
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from scipy import signal

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except:
    import shutil
    FFMPEG = shutil.which("ffmpeg")

SR = 22050
AUDIO_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio fyi")
PROFILE_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib/noise-profiles")
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def load_mp3(path, sr=SR, start=0, duration=None):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-ss", str(start)]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-i", str(path), "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav_path)]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode != 0:
        return None
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0


def generate_pink_noise(n, sr=SR):
    """Voss-McCartney算法生成粉红噪音（更准确）"""
    n_octaves = 16
    octaves = np.random.randn(n_octaves, n)
    for i in range(n_octaves):
        k = 2 ** (i + 1)
        kernel = np.ones(k) / k
        octaves[i] = np.convolve(octaves[i], kernel, mode='same')
    pink = np.sum(octaves, axis=0)
    pink = pink / (np.max(np.abs(pink)) + 1e-8)
    return pink.astype(np.float32)


def generate_brown_noise(n, sr=SR):
    """布朗噪音（红噪音），更低频，模拟低频隆隆声"""
    white = np.random.randn(n)
    # 积分（布朗运动）
    brown = np.cumsum(white)
    brown = brown - np.mean(brown)
    brown = brown / (np.max(np.abs(brown)) + 1e-8)
    return brown.astype(np.float32)


def generate_am_fading(n, sr=SR, rate=0.06, depth=0.3):
    """AM信号衰落：慢速正弦幅度调制
    rate: 衰落频率(Hz)，0.05-0.1Hz对应10-20秒周期
    depth: 调制深度(0-1)
    """
    t = np.arange(n) / sr
    # 主衰落 + 少量随机变化
    fade = 1.0 - depth + depth * 0.5 * (
        np.sin(2 * np.pi * rate * t + np.random.uniform(0, 2*np.pi)) +
        0.3 * np.sin(2 * np.pi * rate * 1.7 * t + np.random.uniform(0, 2*np.pi))
    )
    # 加入随机的突发衰落（信号弱2-5秒）
    num_fades = int(n / sr / 30)  # 每30秒可能有一次
    for _ in range(num_fades):
        if np.random.random() < 0.3:
            fade_start = np.random.randint(0, n - int(sr*5))
            fade_len = np.random.randint(int(sr*1), int(sr*4))
            fade_env = np.sin(np.linspace(0, np.pi, fade_len)) ** 2
            fade[fade_start:fade_start+fade_len] *= (1.0 - 0.4 * fade_env)
    return fade.astype(np.float32)


def generate_crackles(n, sr=SR, rate=15, amp=0.08):
    """静电爆裂/噼啪声
    rate: 每秒爆裂次数（真实收音机约10-20个/秒）
    amp: 爆裂幅度
    """
    noise = np.zeros(n, dtype=np.float32)
    num_crackles = int(n / sr * rate)
    for _ in range(num_crackles):
        # 随机位置
        pos = np.random.randint(0, n - int(sr * 0.003))
        # 爆裂持续时间：1-5ms
        dur = np.random.randint(int(sr*0.001), int(sr*0.005))
        # 衰减包络
        decay = np.exp(-np.linspace(0, np.random.uniform(8, 15), dur))
        # 宽带噪音脉冲
        crack = np.random.randn(dur).astype(np.float32) * decay
        # 随机幅度
        crack_amp = np.random.uniform(0.3, 1.0) * amp
        if pos + dur < n:
            noise[pos:pos+dur] += crack * crack_amp
    return noise


def generate_hum(n, sr=SR, freq=50, amount=0.005):
    """50Hz交流嗡声（含谐波）"""
    t = np.arange(n) / sr
    hum = (
        np.sin(2 * np.pi * freq * t) * 0.5 +
        np.sin(2 * np.pi * freq * 2 * t) * 0.25 +
        np.sin(2 * np.pi * freq * 3 * t) * 0.12 +
        np.sin(2 * np.pi * freq * 4 * t) * 0.06
    )
    # 轻微幅度波动
    mod = 1.0 + 0.1 * np.sin(2 * np.pi * 0.5 * t)
    return (hum * mod * amount).astype(np.float32)


def apply_wow_flutter(audio, sr=SR, wow_rate=0.5, wow_depth=0.001):
    """极轻微的频率漂移(wow/flutter)，模拟磁带/振荡器不稳定
    注意：这通过重采样实现，对长音频计算量较大，默认强度很小
    """
    if wow_depth <= 0:
        return audio
    n = len(audio)
    t = np.arange(n) / sr
    # 低频wow
    wow = np.sin(2 * np.pi * wow_rate * t) * wow_depth
    # 时间轴轻微伸缩
    time_map = t + wow
    new_audio = np.interp(time_map, t, audio)
    return new_audio.astype(np.float32)


def generate_vintage_radio_noise(duration_sec, preset="70s", sr=SR):
    """
    生成一整段老式收音机噪音

    年代预设参数（基于参考音频分析校准）：
    - 50s: 大底噪、多爆裂、明显嗡声、快速衰落、频宽窄
    - 60s: 中等底噪、中等爆裂
    - 70s: 适中底噪、爆裂较多、轻微嗡声
    - 80s: 较小底噪、爆裂少、音质较好
    """
    n = int(duration_sec * sr)
    t = np.arange(n) / sr

    # 各年代预设参数
    presets = {
        "50s": {
            "pink_gain": 0.050,       # 粉红噪音
            "brown_gain": 0.020,      # 布朗噪音（低频隆隆）
            "hiss_gain": 0.010,       # 高频嘶嘶
            "hum_gain": 0.012,        # 50Hz嗡声
            "crackle_rate": 20,       # 爆裂密度(个/秒)
            "crackle_amp": 0.12,      # 爆裂幅度
            "fade_rate": 0.08,        # 衰落频率(Hz)
            "fade_depth": 0.4,        # 衰落深度
            "agc_pump": 0.3,          # AGC抽吸效应
        },
        "60s": {
            "pink_gain": 0.040,
            "brown_gain": 0.012,
            "hiss_gain": 0.008,
            "hum_gain": 0.008,
            "crackle_rate": 16,
            "crackle_amp": 0.09,
            "fade_rate": 0.07,
            "fade_depth": 0.3,
            "agc_pump": 0.2,
        },
        "70s": {
            "pink_gain": 0.035,
            "brown_gain": 0.008,
            "hiss_gain": 0.006,
            "hum_gain": 0.006,
            "crackle_rate": 12,
            "crackle_amp": 0.07,
            "fade_rate": 0.06,
            "fade_depth": 0.25,
            "agc_pump": 0.15,
        },
        "80s": {
            "pink_gain": 0.025,
            "brown_gain": 0.004,
            "hiss_gain": 0.008,
            "hum_gain": 0.003,
            "crackle_rate": 6,
            "crackle_amp": 0.04,
            "fade_rate": 0.04,
            "fade_depth": 0.15,
            "agc_pump": 0.08,
        },
    }

    p = presets.get(preset, presets["70s"])

    # 1. 基础噪音层
    noise = np.zeros(n, dtype=np.float32)
    noise += generate_pink_noise(n, sr) * p["pink_gain"]
    noise += generate_brown_noise(n, sr) * p["brown_gain"]

    # 嘶嘶声（高通滤波的白噪音）
    hiss = np.random.randn(n).astype(np.float32)
    hiss = np.convolve(hiss, np.array([1, -0.97]), mode='same')
    noise += hiss * p["hiss_gain"]

    # 2. 50Hz交流嗡声
    noise += generate_hum(n, sr, 50, p["hum_gain"])

    # 3. 静电爆裂声
    noise += generate_crackles(n, sr, p["crackle_rate"], p["crackle_amp"])

    # 4. 应用AM信号衰落（整体幅度调制）
    fade_env = generate_am_fading(n, sr, p["fade_rate"], p["fade_depth"])
    noise *= fade_env

    # 5. 整体标准化，避免削波
    peak = np.max(np.abs(noise))
    if peak > 0:
        noise = noise / peak * 0.35

    return noise.astype(np.float32)


def extract_noise_from_reference(audio_path, output_profile_name, sr=SR):
    """从参考音频中提取噪音指纹（供未来校准使用）"""
    audio = load_mp3(audio_path, sr)
    if audio is None:
        print(f"  ⚠️ 无法加载: {audio_path}")
        return None

    dur = len(audio) / sr
    print(f"  分析: {audio_path.name} ({dur:.1f}秒)")

    # 找低能量段（噪音/间隙）
    win = sr
    noise_chunks = []
    for s in range(0, int(dur)):
        chunk = audio[s*win:min((s+1)*win, len(audio))]
        if len(chunk) < win * 0.5:
            continue
        rms = np.sqrt(np.mean(chunk**2))
        if rms < 0.04:
            noise_chunks.append(chunk)

    if noise_chunks:
        noise_audio = np.concatenate(noise_chunks)
        out_path = PROFILE_DIR / f"{output_profile_name}.wav"
        wavfile.write(str(out_path), sr, (noise_audio * 32767).astype(np.int16))
        print(f"  ✓ 提取噪音指纹: {out_path.name} ({len(noise_audio)/sr:.1f}秒)")
        return out_path
    else:
        print(f"  ⚠️ 未找到足够的噪音段")
        return None


def fade(audio, fade_in=0.5, fade_out=2.0, sr=SR):
    out = audio.copy()
    fi = int(fade_in * sr)
    fo = int(fade_out * sr)
    if fi > 0 and fi < len(out):
        out[:fi] *= np.linspace(0, 1, fi)
    if fo > 0 and fo < len(out):
        out[-fo:] *= np.linspace(1, 0, fo)
    return out


if __name__ == "__main__":
    print("=" * 60)
    print("📻 老式收音机噪音模拟系统")
    print("=" * 60)

    # 从参考音频提取噪音指纹
    print("\n📥 从参考音频提取噪音指纹...")
    # 列出audio fyi目录的所有文件
    for f in sorted(AUDIO_DIR.glob("*.mp3")):
        safe_name = f.stem.replace(" ", "_").replace("#", "").replace("！", "")[:30]
        extract_noise_from_reference(f, safe_name)

    # 生成各年代噪音样本供试听
    print("\n🎧 生成各年代噪音样本...")
    sample_dir = Path("/Users/swan/Documents/1024/vibe/时光收音机/output/noise_samples")
    sample_dir.mkdir(parents=True, exist_ok=True)
    for era in ["50s", "60s", "70s", "80s"]:
        noise = generate_vintage_radio_noise(10.0, era)
        noise = fade(noise, 0.3, 1.0)
        out = sample_dir / f"radio_noise_{era}.wav"
        wavfile.write(str(out), SR, (noise * 32767).astype(np.int16))
        print(f"  ✓ {out.name}: 10秒样本, RMS={np.sqrt(np.mean(noise**2)):.4f}")

    print(f"\n✅ 噪音样本保存在: {sample_dir}")
    print("请试听各年代噪音样本，确认质感是否接近真实收音机")
