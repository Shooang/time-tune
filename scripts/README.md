# 时光调频 · 音频生成工具使用说明

## 快速开始

### 1. 安装依赖

```bash
# 进入项目目录
cd "/Users/swan/Documents/1024/vibe/时光收音机"

# 安装 Python 依赖
pip3 install edge-tts scipy numpy

# 可选：安装 pydub（更好的音频格式支持）
pip3 install pydub

# macOS 可选：安装 ffmpeg（更好的音频处理）
brew install ffmpeg
```

### 2. 生成测试音频

```bash
# 方式 A：使用纯 Python 版本（不需要 ffmpeg）
python3 scripts/generate_vintage_audio_python.py

# 方式 B：使用 FFmpeg 版本（效果更好）
python3 scripts/generate_vintage_audio.py
```

### 3. 试听输出

生成的音频文件位于 `outputs/` 目录：

```
outputs/
├── vintage_vintage_50s.mp3   # 50年代版本（最老旧）
├── vintage_vintage_60s.mp3   # 60年代版本
├── vintage_vintage_70s.mp3   # 70年代版本（参考音频风格）
└── vintage_vintage_80s.mp3   # 80年代版本（稍清晰）
```

## 高级用法

### 生成所有年代感版本

```bash
python3 scripts/generate_vintage_audio_python.py --all-presets
```

### 自定义音色

```bash
# 男声（推荐用于播音腔）
python3 scripts/generate_vintage_audio_python.py -v zh-CN-YunyangNeural

# 女声
python3 scripts/generate_vintage_audio_python.py -v zh-CN-XiaoxiaoNeural
```

### 自定义预设

```bash
# 50年代效果（最老旧）
python3 scripts/generate_vintage_audio_python.py -p vintage_50s

# 80年代效果（稍清晰）
python3 scripts/generate_vintage_audio_python.py -p vintage_80s
```

### 自定义文本

```bash
python3 scripts/generate_vintage_audio_python.py -t "这是我的自定义广播稿内容..."
```

## 可用音色

| 音色 ID | 性别 | 风格 | 推荐用途 |
|---------|------|------|---------|
| `zh-CN-YunyangNeural` | 男声 | 标准播音员 | ⭐ 播音腔（推荐） |
| `zh-CN-YunzeNeural` | 男声 | 自然流畅 | 年轻人声音 |
| `zh-CN-XiaoxiaoNeural` | 女声 | 标准播音员 | 女声播音 |
| `zh-CN-XiaoyiNeural` | 女声 | 自然流畅 | 年轻女性声音 |

## 可用预设

| 预设 | 带通范围 | 底噪 | 失真 | 适用场景 |
|------|---------|------|------|---------|
| `vintage_50s` | 300-3000Hz | 0.025 | 0.30 | 50 年代（最老旧） |
| `vintage_60s` | 300-3200Hz | 0.020 | 0.25 | 60 年代 |
| `vintage_70s` | 350-3400Hz | 0.015 | 0.20 | 70 年代（参考音频风格） |
| `vintage_80s` | 400-4000Hz | 0.010 | 0.15 | 80 年代（稍清晰） |

## 年代感效果说明

年代感效果包含以下处理：

1. **带通滤波**：模拟老式收音机的频响范围（300-3400Hz），去除高频和低频
2. **谐波失真**：模拟电子管放大器的温暖感
3. **底噪**：添加粉红噪音，模拟收音机的背景沙沙声
4. **归一化**：防止音频削波，保持合适音量

## 常见问题

### Q: 提示 "edge-tts 未安装"

```bash
pip3 install edge-tts
```

### Q: 提示 "scipy 未安装"

```bash
pip3 install scipy numpy
```

### Q: 提示 "ffmpeg 未安装"

```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows
# 下载 https://ffmpeg.org/download.html
```

### Q: 如何试听后与参考音频对比？

请在 `audio fyi/` 目录中找到参考音频，然后与 `outputs/` 中的生成音频对比。

推荐对比顺序：
1. 试听参考音频 `audio fyi/再来听一听70代中央人民广播电台...mp3`
2. 试听生成的 `outputs/vintage_vintage_70s.mp3`
3. 对比两者的年代感差异

### Q: 效果不够"老"怎么办？

尝试更"老"的预设：

```bash
# 从 vintage_70s 改为 vintage_60s
python3 scripts/generate_vintage_audio_python.py -p vintage_60s

# 或 vintage_50s（最老）
python3 scripts/generate_vintage_audio_python.py -p vintage_50s
```

### Q: 效果太"老"怎么办？

尝试更"新"的预设：

```bash
# 从 vintage_70s 改为 vintage_80s
python3 scripts/generate_vintage_audio_python.py -p vintage_80s
```

## 下一步

1. 试听生成的音频
2. 与参考音频（`audio fyi/`）对比
3. 告诉我哪个预设最接近你想要的"年代感"
4. 如果需要调整，告诉我具体的偏好（更老/更清晰）
