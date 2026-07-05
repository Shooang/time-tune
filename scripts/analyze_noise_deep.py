#!/usr/bin/env python3
"""
深度分析参考音频的噪音特征：
1. 从参考音频中提取静音/噪音段（无人声、无音乐的段）
2. 分析这些噪音段的频谱特征、动态范围、调制特性
3. 生成噪音指纹(noise profile)，用于后续模拟
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

AUDIO_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio fyi")
SR = 22050

def load_mp3(path, sr=SR):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        wav_path = Path(f.name)
    cmd = [FFMPEG, "-y", "-i", str(path), "-ac", "1", "-ar", str(sr), "-acodec", "pcm_s16le", str(wav_path)]
    subprocess.run(cmd, capture_output=True, timeout=120)
    sr_out, data = wavfile.read(str(wav_path))
    wav_path.unlink()
    return data.astype(np.float32) / 32768.0


def analyze_noise_profile(audio, sr, label=""):
    """分析一段噪音的特征"""
    print(f"\n{'='*60}")
    print(f"📊 噪音特征分析: {label}")
    print(f"{'='*60}")

    dur = len(audio) / sr
    print(f"  时长: {dur:.2f}秒")
    print(f"  RMS能量: {np.sqrt(np.mean(audio**2)):.4f}")
    print(f"  峰值: {np.max(np.abs(audio)):.4f}")
    print(f"  动态范围: {20*np.log10(np.max(np.abs(audio))/(np.sqrt(np.mean(audio**2))+1e-10)):.1f}dB")

    # 频谱分析
    f, Pxx = signal.welch(audio, sr, nperseg=4096)
    # 分频段能量
    bands = {
        "50-100Hz(交流嗡声)": (50, 100),
        "100-300Hz(低频)": (100, 300),
        "300-1000Hz(中频)": (300, 1000),
        "1000-3000Hz(中高频)": (1000, 3000),
        "3000-8000Hz(高频嘶嘶)": (3000, 8000),
    }
    total_energy = np.sum(Pxx)
    print(f"\n  频段能量分布:")
    for name, (fmin, fmax) in bands.items():
        mask = (f >= fmin) & (f <= fmax)
        energy = np.sum(Pxx[mask]) / total_energy * 100
        bar = "█" * int(energy / 2)
        print(f"    {name:20s}: {energy:5.1f}% {bar}")

    # 检查50Hz谐波分量强度
    for hz in [50, 100, 150, 200]:
        idx = np.argmin(np.abs(f - hz))
        peak = Pxx[idx]
        # 附近平均值
        nearby = np.mean(Pxx[max(0,idx-5):min(len(Pxx),idx+5)])
        ratio = peak / (nearby + 1e-10)
        print(f"  {hz}Hz分量: 峰值/附近平均 = {ratio:.1f}x {'(明显嗡声)' if ratio > 3 else ''}")

    # 时间调制分析（信号衰落特性）
    # 用100ms窗口计算能量包络
    win = int(0.1 * sr)
    if len(audio) > win:
        envelope = []
        for i in range(0, len(audio)-win, win//2):
            chunk = audio[i:i+win]
            envelope.append(np.sqrt(np.mean(chunk**2)))
        envelope = np.array(envelope)
        env_mod = np.std(envelope) / (np.mean(envelope) + 1e-10)
        print(f"\n  能量包络调制深度: {env_mod:.3f} {'(有明显起伏/衰落)' if env_mod > 0.3 else '(较平稳)'}")

        # 分析调制频率（衰落速率）
        if len(envelope) > 20:
            env_fft = np.abs(np.fft.rfft(envelope - np.mean(envelope)))
            env_f = np.fft.rfftfreq(len(envelope), 0.05)  # 20Hz采样率
            peak_mod_idx = np.argmax(env_fft[1:]) + 1
            if peak_mod_idx < len(env_f):
                print(f"  主要调制频率: {env_f[peak_mod_idx]:.2f}Hz (信号衰落/起伏速率)")

    # 检测脉冲/爆裂声密度
    # 用短窗口(1ms)检测突发能量
    short_win = int(0.001 * sr)
    if len(audio) > short_win * 100:
        short_rms = []
        for i in range(0, len(audio)-short_win, short_win*5):
            chunk = audio[i:i+short_win]
            short_rms.append(np.sqrt(np.mean(chunk**2)))
        short_rms = np.array(short_rms)
        median_rms = np.median(short_rms)
        # 超过中值3倍的视为爆裂
        crackle_count = np.sum(short_rms > median_rms * 3)
        crackle_rate = crackle_count / (len(audio) / sr)
        print(f"  爆裂/脉冲密度: {crackle_rate:.1f}个/秒")

    return {
        "duration": dur,
        "rms": float(np.sqrt(np.mean(audio**2))),
        "peak": float(np.max(np.abs(audio))),
        "dynamic_range_db": float(20*np.log10(np.max(np.abs(audio))/(np.sqrt(np.mean(audio**2))+1e-10))),
        "crackle_rate": float(crackle_rate) if len(audio) > short_win * 100 else 0,
    }


print("=" * 60)
print("🔍 时光调频 - 参考音频噪音深度分析")
print("=" * 60)

# 分析所有参考音频
ref_files = [
    ("再来听一听70代中央人民广播电台广播新闻和报纸摘要节目原声 #老物件老情怀.mp3", "70年代中央台新闻"),
    ("1984.mp3", "1984年广播"),
    ("年代广播参考.mp3", "年代广播参考(长音频)"),
]

for fname, label in ref_files:
    fpath = AUDIO_DIR / fname
    if not fpath.exists():
        print(f"⚠️ 文件不存在: {fname}")
        continue
    print(f"\n\n📂 加载: {fname}")
    audio = load_mp3(fpath)
    dur = len(audio) / SR
    print(f"  总时长: {dur:.1f}秒")

    # 1. 找低能量段（可能是纯噪音/静音段）
    win = SR  # 1秒窗口
    noise_segments = []
    speech_segments = []
    music_segments = []

    for s in range(0, int(dur)):
        chunk = audio[s*win:min((s+1)*win, len(audio))]
        if len(chunk) < win * 0.5:
            continue
        rms = np.sqrt(np.mean(chunk**2))

        # 频谱特征判断
        f, Pxx = signal.welch(chunk, SR, nperseg=min(2048, len(chunk)))
        high_energy_ratio = np.sum(Pxx[f > 2000]) / (np.sum(Pxx) + 1e-10)

        # 简单分类：低能量+低高频比=噪音/静音
        if rms < 0.03:
            noise_segments.append(chunk)
        elif high_energy_ratio > 0.3:
            music_segments.append(chunk)
        else:
            speech_segments.append(chunk)

    print(f"  检测到: {len(noise_segments)}个噪音/静音段, {len(speech_segments)}个语音段, {len(music_segments)}个音乐段")

    # 如果找到噪音段，分析它们
    if noise_segments:
        noise_audio = np.concatenate(noise_segments)
        if len(noise_audio) > SR * 0.5:
            analyze_noise_profile(noise_audio, SR, f"{label} - 噪音段")

    # 也分析一段语音+背景（取语音段的开头/结尾部分，那里噪音更明显）
    if speech_segments:
        # 取语音段，用频谱减法估计噪音：语音暂停间隙的噪音
        # 简单方法：取语音段中10-20秒，分析整体频谱（含人声+噪音）
        speech_audio = np.concatenate(speech_segments[:3])
        print(f"\n📊 语音+背景整体分析 ({label}):")
        f_full, Pxx_full = signal.welch(speech_audio[:SR*10], SR, nperseg=4096)
        total_full = np.sum(Pxx_full)
        for name, (fmin, fmax) in [
            ("50-100Hz", (50,100)), ("300-3kHz语音带", (300,3000)), ("3kHz以上嘶声", (3000,8000))
        ]:
            mask = (f_full >= fmin) & (f_full <= fmax)
            print(f"  {name}: {np.sum(Pxx_full[mask])/total_full*100:.1f}%")

print("\n\n" + "=" * 60)
print("✅ 分析完成，特征数据可用于噪音模型校准")
print("=" * 60)
