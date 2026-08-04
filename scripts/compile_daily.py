#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日热点合集脚本生成（shipin-autopilot）
一条视频装多个当天热点：选最热 top N（默认4），每个生成 ~30s 短文案，拼成 ~2 分钟总脚本。

用法:
  python compile_daily.py                     # 读今天 hotspots/*.json，生成合集脚本
  python compile_daily.py --top 5 --target 120   # 5个热点，目标总时长 120s
  python compile_daily.py --date 2026-08-04   # 指定日期
输出:
  scripts/hotspots/<date>_daily_script.txt   # 每行一句（可直喂 TTS）
  scripts/hotspots/<date>_daily_meta.json    # 标题/话题/每段信息
"""
import sys
import io
import os
import json
import glob
import argparse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
HOTSPOTS = BASE / "hotspots"

# 每个热点按赛道的看点句（避免模板重复感）
CATEGORY_ANGLE = {
    "财经": "这消息一出，直接影响了全球市场的情绪，有人已经开始慌了。",
    "科技": "这项技术一旦落地，可能改变我们未来几年的生活方式。",
    "体育": "这消息传开，球迷圈直接炸了，支持和反对的两边谁也说服不了谁。",
    "社会": "这事儿在海外引发巨大争议，各方观点吵成了一锅粥。",
    "明星": "消息一出直接冲上热搜，粉丝和路人的反应两极分化。",
    "综合": "这事儿传开的速度，快得超乎想象，评论区已经吵翻了。",
}


def hotspot_script(title: str, category: str, idx: int, total: int) -> list[str]:
    angle = CATEGORY_ANGLE.get(category, CATEGORY_ANGLE["综合"])
    lines = []
    if idx == 0:
        lines.append("先别划走，今天国外发生了好几件大事，两分钟给你讲完。")
    else:
        lines.append("再说第二条。")
    lines.append(title + "。")
    lines.append(angle)
    lines.append("有人觉得太离谱，有人觉得早该这样，你怎么看？")
    if idx < total - 1:
        lines.append("别急，后面还有更劲爆的。")
    return lines


# 合集标题模板
def make_title(titles: list[str]) -> str:
    # 提取每个标题的核心词（取前 6-10 字，去掉标点）
    import re
    keys = []
    for t in titles[:3]:
        clean = re.sub(r"[^\w\u4e00-\u9fa5]", "", t)
        keys.append(clean[:10])
    return f"今天国外炸了：{keys[0]}、{keys[1] if len(keys)>1 else '这些事'}…两分钟看完全部热点"


def make_topics(categories: list[str]) -> list[str]:
    base = ["#热点", "#国际新闻", "#每日速览", "#吃瓜", "#热搜"]
    for c in categories:
        if c and c != "综合":
            base.append(f"#{c}")
    # 去重保序
    seen, out = set(), []
    for t in base:
        if t not in seen:
            seen.add(t); out.append(t)
    return out[:8]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="", help="日期 YYYY-MM-DD（默认今天）")
    parser.add_argument("--top", type=int, default=4, help="热点数量（默认4）")
    parser.add_argument("--target", type=float, default=120, help="目标总时长秒（默认120）")
    parser.add_argument("--categories", action="store_true", help="按赛道优先选热点")
    args = parser.parse_args()

    # 找热点 json
    date = args.date
    if not date:
        jsons = sorted(glob.glob(str(HOTSPOTS / "*.json")))
        if not jsons:
            print("❌ 没有热点数据，先跑 daily_hotspot.py"); sys.exit(1)
        date = Path(jsons[-1]).stem
    data_file = HOTSPOTS / f"{date}.json"
    if not data_file.exists():
        print(f"❌ 无 {data_file}"); sys.exit(1)

    data = json.load(open(data_file, encoding="utf-8"))
    hot = data.get("hot", data.get("all", []))
    if not hot:
        print("❌ 热点为空"); sys.exit(1)

    # 选 top N（可先按赛道去重）
    selected = hot[: args.top]
    if args.categories:
        seen_cat, dedup = set(), []
        for h in hot:
            c = h.get("category", "综合")
            if c not in seen_cat and len(dedup) < args.top:
                seen_cat.add(c); dedup.append(h)
        if len(dedup) >= 2:
            selected = dedup

    # 生成合集脚本
    all_lines = []
    for idx, h in enumerate(selected):
        all_lines.extend(hotspot_script(h["title"], h.get("category", "综合"), idx, len(selected)))
    # 结尾互动
    all_lines.append("最后问一句：这几个事你最关心哪个？评论区报个数，我下期单独讲。")
    all_lines.append("关注我，每天两分钟，看完全球大事。")

    script_path = HOTSPOTS / f"{date}_daily_script.txt"
    script_path.write_text("\n".join(all_lines), encoding="utf-8")

    # 元信息
    meta = {
        "date": date,
        "hotspots": [{"title": h["title"], "category": h.get("category", ""), "score": h.get("score", 0)} for h in selected],
        "title": make_title([h["title"] for h in selected]),
        "topics": make_topics([h.get("category", "") for h in selected]),
        "script_file": str(script_path),
    }
    meta_path = HOTSPOTS / f"{date}_daily_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"📰 每日热点合集（{date} · {len(selected)} 个热点）")
    for h in selected:
        print(f"  - [{h.get('score')}][{h.get('category','')}] {h['title']}")
    print(f"\n📝 脚本: {script_path}（{len(all_lines)} 句）")
    print(f"🏷️ 标题: {meta['title']}")
    print(f"  话题: {' '.join(meta['topics'])}")


if __name__ == "__main__":
    main()
