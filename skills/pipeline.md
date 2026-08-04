---
name: shipin-pipeline
description: shipin 短视频一体化流水线：文案→小米MiMo配音→B站真实+Pexels混合素材→ffmpeg合成→agnes封面→抖音发布
---

# 短视频一体化工作流（shipin 项目）

从文案到抖音发布的全流程 playbook。输入：热点选题 + 文案；输出：已发布到抖音的成片。

## 流程总览

```
复盘上一作品 → 选题/文案 → 配音(小米MiMo) → 素材(真实画面+通用混搭) → 合成(ffmpeg) → 封面(agnes) → 发布(抖音创作者中心) → 登记复盘
```

## Step 0: 必做——复盘上一作品并落实改进（用户要求）

**每次创作新作品前，必须先做这一步，不可跳过：**

1. 读经验库 `scripts/lessons.md`（最顶部的经验条目）
2. 找上一篇视频的复盘报告：`output/<上一个视频名>/review_*.md`（若无，说明还没复盘，先提示用户或从 review_queue 判断）
3. 汇总上一作品的关键结论：
   - ✅ 做对了什么 → 本作品继续沿用
   - 🔧 哪里卡壳（标题/钩子/完播/评论/素材问题）→ 本作品针对改进
4. **把改进点写进本作品的制作方案**，并在创作过程中落实（如：上一条评论率低 → 本作品结尾加强互动提问）
5. 创作时在回复里主动说明："基于上一条的复盘，本次改进：……"

> 复盘流程见 `/shipin-review`；经验沉淀在 `scripts/lessons.md`。

## 关键路径与配置（先确认存在）

| 资源 | 位置 |
|---|---|
| MoneyPrinterTurbo | `E:\reasonix\money\MoneyPrinterTurbo`（main.py 起 FastAPI :8080；config.toml 配了 Pexels key + deepseek） |
| Pexels 已下载素材 | `E:\reasonix\money\MoneyPrinterTurbo\storage\cache_videos\*.mp4`（169+ 个） |
| 小米 MiMo TTS | `https://api.xiaomimimo.com/v1`，**认证 header `api-key: <key>`**（非 Bearer），模型 `mimo-v2.5-tts`，key 见会话/用户 |
| agnes 生图/识图 | `~/.agnes.json`（base_url/api_key），生图 `POST /v1/images/generations`（agnes-image-2.1-flash），识图 `POST /v1/chat/completions`（agnes-2.5-flash，答案在 reasoning_content） |
| 本地识图（备选） | Ollama `http://127.0.0.1:11434/api/chat`，model `qwen2.5vl:7b`，**content 用 `"images":[base64]` 字段**（不是 image_url！），文本正常但图片请求 400 时检查字段格式 |
| 抖音发布 | 浏览器 `https://creator.douyin.com/creator-micro/content/upload`（nuphus 浏览器，需已登录） |

## Step 1: 文案准备

- 写脚本到 `scripts/<视频名>/script.txt`，**每行一句**（TTS 和字幕都按行处理）
- 短视频文案结构：钩子(3s) → 悬念 → 事件还原 → 背景/冲突 → 升华 → 互动收尾
- 吸睛标题三要素：数字 + 冲突 + 名人；简介结尾带互动提问

## Step 2: 配音（小米 MiMo TTS）

用 MPT venv 的 python（`E:\reasonix\money\MoneyPrinterTurbo\.venv\Scripts\python.exe`，有 edge-tts；系统 python 没有）。

```json
POST /v1/chat/completions
{"model":"mimo-v2.5-tts",
 "messages":[{"role":"user","content":"用清晰自然适合短视频旁白的语气朗读，讲故事感觉"},
             {"role":"assistant","content":"<每句文本>"}],
 "audio":{"format":"wav","voice":"冰糖"}}
```
- 响应：`choices[0].message.audio.data`（base64 wav 24kHz）
- **逐句调用**（每句一个请求），保存 `raw_materials/<name>_tts/sNN.wav`，用 wave 模块读时长
- **中文音色名直接传中文**（"冰糖"），curl 会因 GBK 乱码，**必须用 python urllib 发送**
- 预置音色：冰糖(女清亮)/茉莉(女温柔)/苏打(男活力)/白桦(男沉稳)，TTS 限时免费
- 拼接所有句 → `final.wav`；按累计时长生成 `subtitle_mimo.srt`（每句一条字幕，时间轴从 0 累计）
- 样音参考：`output/<视频名>/voice_samples/`

## Step 3: 素材（真实画面 + 通用素材混搭）

**混搭策略**（用户偏好）：C罗本尊/颁奖/父子真实感镜头用 B站真实画面，钱/表情/少年等通用镜头用 Pexels——既有记忆点又干净。

### 3a. B站真实画面
1. 搜索：nuphus 浏览器打开 `https://search.bilibili.com/all?keyword=<关键词>`（浏览器能过风控，curl/API 会 412/风控）
2. 提取链接：`browser_evaluate` 里 `Array.from(document.querySelectorAll('a[href*="video/BV"]'))...` 去重取 href
3. 下载：`yt-dlp`（已全局安装）格式 `bv*[height<=720]+ba/b[height<=720]`，merge_output_format mp4
   - 中文文件名 ffmpeg 处理会乱码 → **先复制成 ASCII 名**（如 goals20.mp4）到 `raw_materials/ascii/`
4. **必须检查水印/字幕**：ffmpeg 抽帧（`-ss <t> -frames:v 1 -vf scale=300:-1`）→ 本地 vision（或 agnes）逐张确认。B站 UP 主视频常带：底部解说字幕、角落 bilibili 水印、转场文字、ins 截图文字——这些都不能用。球衣 logo/球场广告牌/颁奖台标属画面实景可接受
   - 找到干净时段：同一素材多抽几个时间点（如 10s/60s/150s）直到发现干净窗口
   - 不好用的素材直接弃用换下一个

### 3b. Pexels 通用素材
- 已有缓存：`cache_videos/*.mp4`，素材记录在 `storage/tasks/<task_id>/script.json` 的 `material_sources`（有 search_term/duration）
- **注意素材长度**：裁剪时长超过素材实际长度会截断 → 先 `ffprobe` 查时长，选 duration ≥ 目标时长的
- 新素材：用全局 skill `media-assets`（Pexels API）

### 3c. 镜头规划
- 按文案段落分 8-12 个镜头组，每组指定 (素材, 起始秒, 时长)
- 总时长 = 配音时长（srt 最后一句 end）；各组时长按比例缩放对齐
- 例：12 镜头 = 7 真实 + 5 Pexels 交替

## Step 4: 合成（ffmpeg）

每个镜头裁剪成竖屏 9:16：
```
scale=w='if(gt(a,1080/1920),-2,1080)':h='if(gt(a,1080/1920),1920,-2)':force_original_aspect_ratio=decrease,crop=1080:1920,setsar=1,fps=30,format=yuv420p
```
- 输出 `raw_materials/clips_mix/clipNN.mp4`（libx264 crf20）
- 拼接：`ffmpeg -f concat -safe 0 -i concat.txt -c copy silent_combined.mp4`（concat.txt 用绝对路径）
- 合成成片：
```
ffmpeg -y -i silent_combined.mp4 -i final.wav -filter_complex
  "[0:v]subtitles='<srt路径转义>':force_style='FontName=Microsoft YaHei Bold,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=1.2'[v]"
  -map [v] -map 1:a -c:v libx264 -crf 20 -c:a aac -b:a 192k -shortest out.mp4
```
- srt 路径：`\`→`/`，`:`→`\:`（Windows 绝对路径要转义）
- 输出到 `output/<视频名>/<视频名>_<音色>_混合画面.mp4`

## Step 5: 封面（agnes 生图）

- agnes 生图：prompt 描述竖屏封面 + 大字标题文字（指定文字内容和颜色），size 1024x1024
- 转竖版：`ffmpeg -i cover.png -vf "crop=576:1024:224:0,scale=1080:1920" cover_9x16.jpg`
- 转横版：`scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080` → cover_16x9.jpg
- 用本地 vision 检查文字是否清晰、够不够吸睛

## Step 6: 发布（抖音创作者中心）

1. nuphus 浏览器打开 `https://creator.douyin.com/creator-micro/content/upload`（需已登录）
2. `browser_upload` 上传成片（selector: `input[type="file"]`）
3. 等上传完出现发布表单（checkbox 立即发布/公开 + textbox 标题 + contenteditable 简介）
4. 填标题：`browser_type` 到标题 input
5. 填简介：点 `.zone-container.editor-kit-container` 后 `browser_evaluate` 里 `el.innerText = 简介+话题; el.dispatchEvent(new Event('input',{bubbles:true}))`
   - 简介 = 故事梗概 + 互动提问 + 话题标签（#C罗 #星二代 等）
6. 封面：点"选择封面"→ 封面面板 → 上传竖/横封面图（`input.semi-upload-hidden-input`）
7. 确认预览（标题/简介/话题都在）→ 点"发布"
8. 等待跳转作品管理页，确认"共 N 个作品"出现且状态"审核中"
9. 发布方案存 `output/<视频名>/douyin_publish.md` 复用

## Step 2.5: 声音克隆（小米 MiMo voiceclone，可选）

用音频样本复刻任意音色（对标账号/真人声音）：

```python
POST https://api.xiaomimimo.com/v1/chat/completions
{"model":"mimo-v2.5-tts-voiceclone",
 "messages":[{"role":"user","content":"东北口音，自然聊天语气"},
             {"role":"assistant","content":"要朗读的文案"}],
 "audio":{"format":"wav","voice":"data:audio/wav;base64,<样本base64>"}}
```

- **样本要求**：mp3/wav，base64 后 ≤10MB，MIME 前缀 `data:audio/wav;base64,`
- **风格控制**：user message 传自然语言指令（口音/语气/情绪）
- **坑**：
  - 克隆接口**限流 429 频繁**（约 1-2 次/分钟），脚本要带等待重试（429 → sleep 70s）
  - **逐句生成比整段自然**：整段长文克隆容易语气漂移、长句卡顿（实测某 30 字句生成 18.88s 异常）；逐句 + 句间自然停顿更流畅
  - 长句拆短句：异常长的句子拆成 2 句重生成（"XX。YY。"）
  - 本地路径含 `E:\` 的预测/样本文件**不要上传 GitHub**（predictions/ 已 gitignore）
- ⚠️ **版权**：克隆他人声音用于公开内容需授权；个人测试可随意，商用建议用 `mimo-v2.5-tts-voicedesign`（文本描述设计原创相似音色）

## 踩坑清单（务必注意）

1. **中文路径/文件名**：Windows bash + ffmpeg 对中文名会乱码 → 处理前先转 ASCII 名
2. **curl 发中文 JSON** 会 GBK 乱码 → 用 python urllib
3. **小米 TTS 是 chat/completions + audio 字段**，不是 OpenAI /v1/audio/speech（404）
4. **Ollama 图片用 `images` 字段**，不是 `image_url`（会 400）
5. **Pexels 素材时长不足**会静默截断成片 → 每镜头选素材前 ffprobe 验证
6. **B站素材水印多**：必须逐素材抽帧检查，找干净时段或换素材
7. **agnes 识图批量会超时/504**：单张 + 小图（scale 300）更稳；本地 Ollama 是可靠备选
8. 合成后抽查成片关键帧（本地 vision），确认无原视频字幕残留
