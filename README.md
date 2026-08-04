# ShortVideo AutoPilot 🎬

**从国外热点到抖音成片的全自动短视频流水线**：每日自动采集国外实时热点 → 小米 MiMo 配音 → 混合素材合成 → AI 封面 → 抖音发布 → 隔天复盘迭代。

> 把"热点选题 → 制作 → 发布 → 复盘改进"的闭环全部自动化，你只负责最终确认。

## ✨ 功能特性

- 🤖 **每日自动热点采集**（Windows 计划任务）：抓取网易国际/新浪国际/环球国际，按热度信号词打分排序，输出高热候选
- 🎙️ **小米 MiMo TTS 配音**：逐句生成高自然度中文配音，预置多音色（冰糖/茉莉/苏打/白桦），自动拼接 + 生成字幕
- 🎞️ **混合素材方案**：C罗本尊/颁奖/父子等"真实感"镜头用 B站真实画面，钱/表情/少年等通用镜头用 Pexels 授权素材——既有记忆点又干净
- 🖼️ **AI 封面**：agnes 生图，自动转竖版/横版双封面（抖音流量加成）
- 📤 **抖音自动发布**：浏览器自动化上传、填标题/简介/话题、设封面、发布
- 📊 **隔天复盘**：拉数据 → 看评论区 → 归因分析 → 输出爆款优化建议 → 沉淀经验库
- 🔄 **强制迭代闭环**：每次创作前必读上一篇复盘结论并落实改进

## 📦 项目结构

```
shortvideo-autopilot/
├── scripts/
│   ├── daily_hotspot.py      # 每日热点采集（计划任务调用）
│   ├── pipeline_tts.py       # 小米 MiMo TTS 配音 + 拼接 + 生成字幕
│   ├── pipeline_compose.py   # 镜头裁剪 + 拼接 + 混音 + 烧字幕
│   ├── lessons.md            # 经验库（创作前必读，复盘后必写）
│   └── review_queue.md       # 待复盘队列
└── skills/
    ├── pipeline.md           # 制作流水线 playbook（含踩坑清单）
    └── review.md             # 复盘分析 playbook
```

## 🚀 快速开始

### 依赖
- Python 3.11+
- ffmpeg（需在 PATH）
- 可选：yt-dlp（B站素材下载）、MoneyPrinterTurbo（Pexels 素材缓存，可选）

### 1. 配置 API

```bash
# 小米 MiMo（配音，必配）
export MIMO_API_KEY="你的小米 MiMo API key"   # 获取: platform.xiaomimimo.com

# agnes（封面生图/识图，可选但推荐）
# 配置 ~/.agnes.json:
# {"provider":"agnes","base_url":"https://api.agnes-ai.cn/v1","api_key":"...","models":{"image":"agnes-image-2.1-flash","text":"agnes-2.5-flash"}}
```

### 2. 采集热点

```bash
python scripts/daily_hotspot.py --top 8
# 输出: scripts/hotspots/2026-08-04.md（🔥高热候选 + 全部列表）
```

Windows 定时任务（每天 15:00）：
```powershell
schtasks /Create /TN "shipin_daily_hotspot" /TR "\"C:\Path\to\python3.13.exe\" \"E:\path\to\daily_hotspot.py\"" /SC DAILY /ST 15:00 /F
```

### 3. 配音

```bash
python scripts/pipeline_tts.py 文案.txt output/tts/ 冰糖
# 输出: output/tts/final.wav + subtitle_mimo.srt
```

### 4. 合成

```bash
python scripts/pipeline_compose.py 镜头配置.json output/tts/final.wav subtitle_mimo.srt output/成片.mp4
```

镜头配置示例（`镜头配置.json`）：
```json
[
  {"src": "raw/pexels_video.mp4", "start": 2, "dur": 6.0, "type": "P"},
  {"src": "raw/bilibili_real.mp4", "start": 3, "dur": 12.0, "type": "R"}
]
```
`type`：P = Pexels 通用素材，R = 真实画面素材。脚本按配音总时长自动缩放对齐，检测素材不足。

## 📖 完整工作流（skills）

`skills/pipeline.md` 和 `skills/review.md` 是完整的 playbook（Reasonix skill 格式），包含：

### 制作流水线
1. **Step 0（必做）**：读经验库 + 上一篇复盘报告 → 把改进点写进本作品方案
2. 文案准备（钩子 → 悬念 → 事件 → 冲突 → 升华 → 互动）
3. 小米 MiMo 配音
4. 素材（B站真实画面：yt-dlp 下载 + 逐帧查水印；Pexels 通用：本地缓存）
5. ffmpeg 合成竖屏 9:16
6. agnes 封面（竖+横）
7. 抖音发布（标题/简介/话题自动配好）

### 复盘分析
- 拉数据（播放/点赞/评论/分享/完播率 vs 健康线）
- 评论区分类（共鸣/质疑/对立/提问）
- 归因分析（卡在哪一环）
- 输出优化建议 → 写入经验库 → 反馈下一期

### 爆款通用公式
> **标题** = 数字 + 冲突 + 名人/热词 + 悬念
> **封面** = 大字标题 + 冲突画面 + 高对比色
> **前 3 秒** = 直接抛最大悬念
> **结尾** = 站队式互动提问
> **话题** = 名人 + 泛流量 + 垂直 三组组合
> **发布时间** = 晚 19-21 点

## ⚠️ 踩坑清单（已在 playbook 中详述）

1. Windows 下中文路径/文件名需转 ASCII（ffmpeg 乱码）
2. curl 发中文 JSON 会 GBK 乱码，用 python urllib
3. 小米 MiMo 是 `chat/completions` + `audio` 字段，不是 OpenAI `/v1/audio/speech`
4. Ollama 识图用 `images` 字段，不是 `image_url`
5. B站素材水印多，必须逐帧检查找干净时段
6. 计划任务用 WindowsApps python stub 会静默失败，用完整路径

## 🧩 集成（可选）

本项目的 playbook 设计为可在 [Reasonix](https://reasonix.dev) 中直接作为 skill 使用：
```
~/.reasonix/skills/shipin-pipeline/SKILL.md  ← 复制 skills/pipeline.md
~/.reasonix/skills/shipin-review/SKILL.md    ← 复制 skills/review.md
```

## ⚖️ 版权声明

- 本项目代码 MIT 协议开源
- 脚本本身不包含任何视频素材；B站素材用于个人学习参考，商用请自行确认版权
- 小米 MiMo TTS、agnes、Pexels 均为第三方服务，请遵守各自服务条款

## 📄 License

MIT
