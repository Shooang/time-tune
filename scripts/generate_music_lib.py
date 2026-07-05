#!/usr/bin/env python3
"""
合成年代广播开场音乐和间隔提示音：
- 《东方红》片段（50-70年代开场曲）
- 《歌唱祖国》片段（80年代起开场曲）
- 短促间隔提示音（新闻段落之间）
采用管乐/军乐音色模拟（铜管+木管）
"""

import numpy as np
from pathlib import Path
from scipy.io import wavfile

SR = 22050
LIB_DIR = Path("/Users/swan/Documents/1024/vibe/时光收音机/audio-lib")


def note_freq(note_name, octave=4):
    """音符名称转频率，支持简谱1-7对应do re mi fa sol la si"""
    # C大调映射：1=C, 2=D, 3=E, 4=F, 5=G, 6=A, 7=B
    note_map = {
        '1': 0, '2': 2, '3': 4, '4': 5, '5': 7, '6': 9, '7': 11,
        'do': 0, 're': 2, 'mi': 4, 'fa': 5, 'sol': 7, 'la': 9, 'si': 11
    }
    # A4 = 440Hz, C4 = 261.63Hz
    c4 = 261.6256
    if isinstance(note_name, str):
        n = note_map.get(note_name.lower()[0], 0)
    else:
        n = note_name
    semitone = n + (octave - 4) * 12
    return c4 * (2 ** (semitone / 12))


def brass_note(freq, dur, sr=SR, vibrato=True):
    """铜管音色：基频+奇次谐波+ADSR+轻微颤音"""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)

    # 铜管音色：丰富的奇次谐波
    note = np.sin(2*np.pi*freq*t) * 1.0
    note += np.sin(2*np.pi*freq*2*t) * 0.5
    note += np.sin(2*np.pi*freq*3*t) * 0.3
    note += np.sin(2*np.pi*freq*4*t) * 0.15
    note += np.sin(2*np.pi*freq*5*t) * 0.1
    note += np.sin(2*np.pi*freq*6*t) * 0.05

    # 颤音
    if vibrato and dur > 0.3:
        vib_rate = 5.0
        vib_depth = 0.004
        note *= 1 + vib_depth * np.sin(2*np.pi*vib_rate*t)

    # ADSR包络
    attack = int(0.04 * sr)
    decay = int(0.08 * sr)
    release = int(0.15 * sr)
    n = len(note)

    env = np.ones(n)
    if attack < n:
        env[:attack] = np.linspace(0, 1, attack)
    if decay < n - attack:
        env[attack:attack+decay] = np.linspace(1, 0.75, decay)
    if release < n:
        env[-release:] = np.linspace(env[-release-1] if release < n else 0.75, 0, release)

    return note * env


def organ_note(freq, dur, sr=SR):
    """管风琴/簧风琴音色（温暖、持续，适合老广播）"""
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    note = np.sin(2*np.pi*freq*t) * 0.6
    note += np.sin(2*np.pi*freq*2*t) * 0.3
    note += np.sin(2*np.pi*freq*3*t) * 0.2
    note += np.sin(2*np.pi*freq*4*t) * 0.1
    note += np.sin(2*np.pi*freq*8*t) * 0.05

    attack = int(0.06 * sr)
    release = int(0.2 * sr)
    n = len(note)
    env = np.ones(n)
    if attack < n:
        env[:attack] = np.linspace(0, 1, attack)
    if release < n:
        env[-release:] = np.linspace(1, 0, release)
    return note * env


def play_melody(notes, tempo=100, instrument='brass', sr=SR):
    """
    演奏旋律
    notes: [(note, octave, beats), ...] 或 [(freq, beats), ...]
    tempo: BPM
    """
    beat_dur = 60.0 / tempo
    audio = []
    for note_def in notes:
        if len(note_def) == 3:
            n, octave, beats = note_def
            freq = note_freq(n, octave)
        else:
            freq, beats = note_def
        dur = beats * beat_dur
        if instrument == 'brass':
            audio.append(brass_note(freq, dur))
        elif instrument == 'organ':
            audio.append(organ_note(freq, dur))
        else:
            t = np.linspace(0, dur, int(sr*dur), endpoint=False)
            audio.append(np.sin(2*np.pi*freq*t) * np.linspace(0, 1, len(t)) * np.linspace(1, 0, len(t))[::-1] * 0.3)
    return np.concatenate(audio)


def add_reverb(audio, sr=SR):
    """添加广播混响"""
    delays = [0.05, 0.12, 0.2]
    decays = [0.35, 0.2, 0.1]
    out = audio.copy()
    for d, g in zip(delays, decays):
        s = int(d * sr)
        if s < len(out):
            out[s:] += audio[:-s] * g
    return out / (1 + 0.5)


def fade(audio, fade_in=0.5, fade_out=1.0, sr=SR):
    out = audio.copy()
    fi = int(fade_in * sr)
    fo = int(fade_out * sr)
    if fi < len(out):
        out[:fi] *= np.linspace(0, 1, fi)
    if fo < len(out):
        out[-fo:] *= np.linspace(1, 0, fo)
    return out


def save_wav(audio, path, sr=SR):
    audio = np.clip(audio, -1.0, 1.0)
    audio_int = (audio * 32767 * 0.7).astype(np.int16)
    wavfile.write(str(path), sr, audio_int)
    print(f"  ✓ {path.name}: {len(audio)/sr:.1f}秒")


# ============================================================================
# 《东方红》片段
# ============================================================================
def generate_dongfanghong(dur=8, sr=SR):
    """
    《东方红》开头片段（管乐齐奏）
    简谱（G徵调，以5=G为do，这里用C大调记谱实际是F调或G调）：
    5 5 6 | 2 - - | 1 1 6 | 2 - - |
    东 方  红   太 阳  升
    5 5 6 2 | 1 - - 16 | 2 - - |
    中 国 出 了 个 毛 泽  东
    """
    tempo = 80
    # 旋律: (音符, 八度, 拍数)
    # 东方红用G调（1=G），这里用C大调演奏，整体偏低更厚重
    melody = [
        ('5', 4, 1), ('5', 4, 1), ('6', 4, 2),  # 5 5 6 | 2 - -
        ('2', 5, 4),
        ('1', 5, 1), ('1', 5, 1), ('6', 4, 2),  # 1 1 6 | 2 - -
        ('2', 5, 4),
        ('5', 4, 0.5), ('5', 4, 0.5), ('6', 4, 1), ('2', 5, 2),
        ('1', 5, 2), ('1', 5, 0.5), ('6', 4, 0.5), ('2', 5, 1),
        ('2', 5, 3),
    ]
    brass = play_melody(melody, tempo=tempo, instrument='brass')

    # 加低音（铜管低音齐奏）
    bass_notes = [
        ('1', 3, 4), ('5', 2, 4),
        ('4', 3, 4), ('5', 2, 4),
        ('1', 3, 2), ('1', 3, 2), ('4', 3, 2), ('5', 2, 4),
    ]
    bass = play_melody(bass_notes, tempo=tempo, instrument='organ')

    # 对齐长度
    min_len = min(len(brass), len(bass))
    mixed = brass[:min_len] * 0.6 + bass[:min_len] * 0.4

    # 混响
    mixed = add_reverb(mixed)
    mixed = fade(mixed, 0.3, dur if dur < len(mixed)/SR else 2.0)

    # 如果需要更长，循环
    while len(mixed) < dur * sr:
        mixed = np.concatenate([mixed, mixed * 0.5])
    mixed = mixed[:int(dur * sr)]

    return mixed / np.max(np.abs(mixed)) * 0.5


# ============================================================================
# 《歌唱祖国》片段
# ============================================================================
def generate_gechangzuguoo(dur=10, sr=SR):
    """
    《歌唱祖国》开头片段（军乐/铜管，进行曲速度）
    5 5 5 | 1 1 | 6 5 | 3 - | 5 - |
    五 星 红  旗  迎 风 飘 扬
    1. 5 | 3 - | 3 0 | 1 6 | 6 - |
    胜 利 歌 声 多 么 响 亮
    """
    tempo = 110  # 进行曲速度
    melody = [
        ('5', 4, 1), ('5', 4, 1), ('5', 4, 1),  # 五 星 红
        ('1', 5, 1), ('1', 5, 1),                # 旗 迎
        ('6', 4, 1), ('5', 4, 1),                # 风 飘
        ('3', 5, 2),                              # 扬
        ('5', 4, 1),
        ('1', 5, 0.5), ('5', 4, 0.5),            # 胜 利
        ('3', 5, 2),                              # 歌
        ('3', 5, 0.5), ('0', 4, 0.5),
        ('1', 5, 1), ('6', 4, 1),                # 多 么
        ('6', 4, 4),                              # 响 亮
    ]
    brass = play_melody([
        (n, o, b) if n != '0' else (0, 0, b) for n, o, b in melody
    ], tempo=tempo, instrument='brass')

    # 军乐低音（1-5-1-5进行）
    bass_pattern = [
        ('1', 3, 2), ('5', 2, 2), ('1', 3, 2), ('5', 2, 2),
        ('1', 3, 2), ('5', 2, 2), ('4', 3, 2), ('5', 2, 4),
    ]
    bass = play_melody(bass_pattern, tempo=tempo, instrument='organ')

    min_len = min(len(brass), len(bass))
    mixed = brass[:min_len] * 0.65 + bass[:min_len] * 0.35
    mixed = add_reverb(mixed)
    mixed = fade(mixed, 0.2, 2.5)

    while len(mixed) < dur * sr:
        mixed = np.concatenate([mixed, mixed[:int(4*sr)]*0.3])
    mixed = mixed[:int(dur * sr)]

    return mixed / np.max(np.abs(mixed)) * 0.5


# ============================================================================
# 间隔提示音（短，3-4秒，段落之间用）
# ============================================================================
def generate_bridge_stinger(dur=4, sr=SR):
    """
    广播间隔提示音：短促的3-4个音符，新闻播完一段时的过渡
    类似"叮-咚-当"的广播提示音，或者是开始曲的最后几小节
    参考老广播的间隔信号：通常是简单的和弦分解或旋律提示
    """
    # 用几个音符组成简短提示：1 3 5 - | 5 - - - |（大三和弦琶音）
    tempo = 90
    notes = [
        ('1', 5, 1), ('3', 5, 1), ('5', 5, 2),  # 上行琶音
        ('3', 5, 1), ('1', 5, 3),                  # 解决到主音
    ]
    melody = play_melody(notes, tempo=tempo, instrument='organ')
    melody = add_reverb(melody, sr)
    melody = fade(melody, 0.1, 1.0)

    # 加和弦伴奏
    chord = organ_note(note_freq('1', 4), len(melody)/sr) * 0.15
    chord += organ_note(note_freq('3', 4), len(melody)/sr) * 0.12
    chord += organ_note(note_freq('5', 4), len(melody)/sr) * 0.12
    min_l = min(len(melody), len(chord))
    mixed = melody[:min_l] + chord[:min_l]

    # 调整到所需时长
    if len(mixed) < dur * sr:
        silence = np.zeros(int(dur*sr) - len(mixed))
        mixed = np.concatenate([mixed, silence])
    else:
        mixed = mixed[:int(dur*sr)]

    return mixed / np.max(np.abs(mixed)) * 0.4


def generate_bridge_short(dur=2.5, sr=SR):
    """更短的间隔提示音（2-3秒），用于新闻条目之间"""
    # 两个音符的"叮咚"声
    t = np.linspace(0, dur, int(sr*dur), endpoint=False)
    # 第一个音
    n1_dur = 0.4
    n1 = organ_note(note_freq('5', 5), n1_dur)
    n1 = np.concatenate([n1, np.zeros(len(t) - len(n1))])
    # 第二个音
    n2_start = int(0.35 * sr)
    n2_dur = 0.5
    n2 = organ_note(note_freq('3', 5), n2_dur) * 0.8
    n2_full = np.zeros(len(t))
    n2_full[n2_start:n2_start+len(n2)] = n2
    # 第三个音（主音解决）
    n3_start = int(0.75 * sr)
    n3_dur = 0.8
    n3 = organ_note(note_freq('1', 5), n3_dur) * 0.7
    n3_full = np.zeros(len(t))
    n3_full[n3_start:n3_start+len(n3)] = n3

    mixed = n1 + n2_full + n3_full
    mixed = add_reverb(mixed)
    mixed = fade(mixed, 0.05, 1.0)
    return mixed / np.max(np.abs(mixed)) * 0.35


def main():
    print("=" * 50)
    print("🎵 合成年代广播音乐素材")
    print("=" * 50)

    sig_dir = LIB_DIR / "bgm" / "signature"
    bridge_dir = LIB_DIR / "bgm" / "bridge"
    sig_dir.mkdir(parents=True, exist_ok=True)
    bridge_dir.mkdir(parents=True, exist_ok=True)

    print("\n🎺 生成开场音乐...")
    dfh = generate_dongfanghong(8)
    save_wav(dfh, sig_dir / "opening_dongfanghong.wav")

    gczg = generate_gechangzuguoo(10)
    save_wav(gczg, sig_dir / "opening_gechangzuguoo.wav")

    print("\n🔔 生成间隔提示音...")
    bridge_long = generate_bridge_stinger(5)
    save_wav(bridge_long, bridge_dir / "bridge_stinger.wav")

    bridge_short = generate_bridge_short(3)
    save_wav(bridge_short, bridge_dir / "bridge_short.wav")

    print("\n✅ 音乐素材已生成到:", LIB_DIR)


if __name__ == "__main__":
    main()
