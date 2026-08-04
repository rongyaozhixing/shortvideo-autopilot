#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复盘 AI 分析脚本：评论 + 数据 → 归因 + 经验条目（自动写入 lessons.md）
用法:
  python review_analyze.py <视频名> [--comments "评论1|评论2|..."] [--data "播放:123,点赞:45,评论:12"]
输出:
  - output/<视频名>/review_<日期>.md  复盘报告
  - scripts/lessons.md               经验条目自动追加
"""
import sys
import io
import os
import json
import argparse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from config import VisionConfig
    AGNES_BASE = VisionConfig.AGNES_VISION_MODEL and "https://api.agnes-ai.cn/v1"
except Exception:
    AGNES_BASE = "https://api.agnes-ai.cn/v1"

BASE = Path(__file__).resolve().parent.parent  # 项目根
LESSONS_FILE = BASE / "scripts" / "lessons.md"


def call_llm(prompt: str, system: str = "") -> str:
    """调 agnes LLM（识别/分析用 agnes-2.5-flash）"""
    import json as j
    key = os.environ.get("AGNES_API_KEY", "")
    if not key:
        # 尝试从 ~/.agnes.json 读取
        home_cfg = Path.home() / ".agnes.json"
        if home_cfg.exists():
            try:
                key = j.load(open(home_cfg, encoding="utf-8"))["api_key"]
            except Exception:
                pass
    if not key:
        return "⚠️ 未配置 AGNES_API_KEY，跳过 AI 分析（仅生成数据报告）"

    model = os.environ.get("AGNES_VISION_MODEL", "agnes-2.5-flash")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1500,
    }
    if system:
        payload["messages"].insert(0, {"role": "system", "content": system})
    req = urllib.request.Request(
        AGNES_BASE + "/chat/completions",
        data=j.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        resp = j.load(urllib.request.urlopen(req, timeout=120))
        msg = resp["choices"][0]["message"]
        return msg.get("reasoning_content") or msg.get("content") or ""
    except Exception as e:
        return f"⚠️ AI 分析失败: {e}"


def append_lesson(title: str, entry: str):
    """把经验条目追加到 lessons.md"""
    if not LESSONS_FILE.exists():
        LESSONS_FILE.write_text("# 短视频经验库\n\n", encoding="utf-8")
    content = LESSONS_FILE.read_text(encoding="utf-8")
    block = f"\n### {datetime.now().strftime('%Y-%m-%d')} | {title}\n{entry}\n"
    # 插到"经验条目"标题之后、最前面（新→旧）
    marker = "## 经验条目（新→旧）\n"
    if marker in content:
        content = content.replace(marker, marker + block, 1)
    else:
        content += block
    LESSONS_FILE.write_text(content, encoding="utf-8")
    return LESSONS_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_name", help="视频名（目录名）")
    parser.add_argument("--comments", default="", help="评论区文本，用 | 分隔多条")
    parser.add_argument("--data", default="", help="数据，格式: 播放:123,点赞:45,评论:12,分享:3")
    args = parser.parse_args()

    # 解析数据
    data = {}
    for kv in args.data.split(","):
        if ":" in kv:
            k, v = kv.split(":", 1)
            data[k.strip()] = v.strip()

    # 1) AI 分析评论
    analysis = ""
    if args.comments:
        comments = args.comments.split("|")
        prompt = (
            "你是短视频运营专家。以下是某条抖音视频的评论区（按热度排序）。\n"
            "请分析并输出：\n"
            "1. 观众高频诉求/共鸣点（哪些评论点赞多、说明什么）\n"
            "2. 槽点/质疑点（是否有争议、事实疑问）\n"
            "3. 观众感兴趣想继续看的内容方向（可直接作为下一期选题）\n"
            "4. 这条视频做对/做错的地方（从评论反推）\n"
            "用简洁中文分点输出。\n\n评论区：\n" + "\n".join(f"- {c}" for c in comments)
        )
        analysis = call_llm(prompt)

    # 2) 生成归因（基于数据 + AI 分析）
    reasons = []
    if data:
        play = int(data.get("播放", 0) or 0)
        like = int(data.get("点赞", 0) or 0)
        comment = int(data.get("评论", 0) or 0)
        if play > 0 and like > 0:
            like_rate = like / play
            if like_rate < 0.03:
                reasons.append(f"点赞率 {like_rate:.1%} 偏低（<3%），内容缺价值点/共鸣点")
            elif like_rate > 0.05:
                reasons.append(f"点赞率 {like_rate:.1%} 不错（>5%），内容有价值")
            else:
                reasons.append(f"点赞率 {like_rate:.1%} 中等（3%-5%），中规中矩")
        if play > 0 and comment > 0:
            comment_rate = comment / play
            if comment_rate < 0.005:
                reasons.append(f"评论率 {comment_rate:.1%} 偏低（<0.5%），互动钩子不足")
            elif comment_rate > 0.01:
                reasons.append(f"评论率 {comment_rate:.1%} 不错（>1%），互动设计有效")
        if play == 0:
            reasons.append("播放为 0，可能仍在审核或限流，需检查")
    if not reasons:
        reasons.append("数据不足，需登录创作者中心补全播放/完播数据")

    # 3) 写复盘报告
    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = BASE / "output" / args.video_name
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / f"review_{today}.md"
    report.write_text(
        f"""# 复盘报告 {today} | {args.video_name}

## 数据
{chr(10).join(f"- {k}: {v}" for k, v in data.items()) if data else "- 未提供数据"}

## AI 评论分析
{analysis if analysis else "- 未提供评论"}

## 归因
{chr(10).join(f"- {r}" for r in reasons)}

## 下一期优化
- （待补充）
""",
        encoding="utf-8",
    )
    print(f"📄 复盘报告: {report}")

    # 4) 写经验条目
    entry = f"""
- ✅ 做对了：{('点赞率高' if any('不错' in r for r in reasons) else '待复盘确认')}
- 🔧 改进：{('；'.join(r for r in reasons if '偏低' in r or '不足' in r) or '待补充')}
- 🧪 下一条要试：{('评论区建议方向：' + analysis[:100] if analysis and '⚠️' not in analysis else '待补充')}
"""
    lesson_file = append_lesson(args.video_name, entry)
    print(f"📚 经验库已更新: {lesson_file}")


if __name__ == "__main__":
    main()
