#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""盲预测脚本（shipin-autopilot · cheat 方法论）
发布前对文案打分 + 写预测，落盘 predictions/<视频名>.md，之后不可修改（immutable）。

用法:
  python predict.py <文案.md|txt> [--title 视频标题] [--scores 4,5,4,5,4]
流程:
  1. 展示 rubric 五维说明
  2. 打分（交互输入，或 --scores 直接给）
  3. 写预测（预期播放/点赞/评论区间 + 一句话 bet）
  4. 落盘 predictions/<标题>.md（含 immutable 标记）
"""
import sys
import io
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
PREDICTIONS_DIR = BASE / "predictions"
RUBRIC = BASE / "scripts" / "rubric.md"

DIMS = [
    ("选题热度", "全球级名人/热点=5 … 无传播性=0"),
    ("钩子强度", "前3秒抛悬念=5 … 不知所云=0"),
    ("结构节奏", "每10-15s一个信息点=5 … 逻辑混乱=0"),
    ("互动钩子", "站队提问=5 … 无结尾=0"),
    ("话题标签", "名人+泛流量+垂直=5 … 无标签=0"),
]


def read_script(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)
    return p.read_text(encoding="utf-8")


def interactive_scores() -> list[int]:
    print("\n=== rubric 打分（每维 0-5）===")
    scores = []
    for i, (name, hint) in enumerate(DIMS, 1):
        while True:
            try:
                v = int(input(f"[{i}/5] {name} ({hint}): ").strip())
                if 0 <= v <= 5:
                    scores.append(v)
                    break
                print("  ⚠️ 0-5 之间")
            except (ValueError, EOFError):
                print("  ⚠️ 输入数字 0-5")
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("script", help="文案文件路径")
    parser.add_argument("--title", default="", help="视频标题（默认用文件名）")
    parser.add_argument("--scores", default="", help="直接给分数，逗号分隔如 4,5,4,5,4")
    parser.add_argument("--play", default="", help="预测播放区间如 30000-80000")
    parser.add_argument("--like", default="", help="预测点赞区间")
    parser.add_argument("--bet", default="", help="一句话 bet")
    args = parser.parse_args()

    script = read_script(args.script)
    title = args.title or Path(args.script).stem

    if args.scores:
        scores = [int(x) for x in args.scores.split(",")]
        if len(scores) != 5:
            print("❌ --scores 需要 5 个分数"); sys.exit(1)
    else:
        print("\n📄 文案预览:")
        print(script[:400] + ("..." if len(script) > 400 else ""))
        scores = interactive_scores()

    total = sum(scores)
    # 权重：钩子1.2 互动1.2 标签0.6，其他1.0 → 加权总分
    weights = [1.0, 1.2, 1.0, 1.2, 0.6]
    weighted = round(sum(s * w for s, w in zip(scores, weights)) / sum(weights), 1)

    # 预测区间（默认按加权分估算）
    if not args.play:
        if weighted >= 4.0: play = "50000+"
        elif weighted >= 3.0: play = "10000-50000"
        elif weighted >= 2.0: play = "3000-10000"
        else: play = "0-3000"
    else:
        play = args.play
    like = args.like or f"≈播放×{0.03 if weighted >= 3 else 0.015:.0%}"
    bet = args.bet or "（待填写一句话判断）"

    # 落盘（immutable）
    PREDICTIONS_DIR.mkdir(exist_ok=True)
    now = datetime.now()
    fname = f"{now.strftime('%Y%m%d')}-{title}.md"
    # 标题里的特殊字符
    fname = "".join(c for c in fname if c not in '\\/:*?"<>|')
    out = PREDICTIONS_DIR / fname

    content = f"""# 预测文件（盲预测 · immutable）

> ⚠️ 本文档在发布**前**完成打分与预测。`## 预测` 段一经写入**不可修改**；
> 发布后只能在 `## 复盘` 段追加实际数据。违反此规则 = 校准循环失效。

## 元信息
- 标题: {title}
- 文案: {args.script}
- 打分时间: {now.strftime('%Y-%m-%d %H:%M')}
- Rubric 版本: v1

## 打分
| 维度 | 分数 |
|---|---|
| 选题热度 | {scores[0]}/5 |
| 钩子强度 | {scores[1]}/5 |
| 结构节奏 | {scores[2]}/5 |
| 互动钩子 | {scores[3]}/5 |
| 话题标签 | {scores[4]}/5 |
| **加权总分** | **{weighted}/5** |

## 预测
- 预期播放: {play}
- 预期点赞: {like}
- 一句话 bet: {bet}

## 复盘
- 实际播放:
- 实际点赞:
- 实际评论:
- 实际分享:
- 预测误差分析:
- 结论（做对/做错）:
"""
    out.write_text(content, encoding="utf-8")
    print(f"\n✅ 预测已落盘: {out}")
    print(f"   加权总分: {weighted}/5 | 预期播放: {play}")
    print("   ⚠️ 记得：发布后只能追加 ## 复盘 段，不能改 ## 预测 段")


if __name__ == "__main__":
    main()
