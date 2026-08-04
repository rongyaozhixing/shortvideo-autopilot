#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国外实时热点采集（shipin 项目）
每天定时抓取国内可达的国外热点源（网易国际/新浪国际/环球网），
按热度信号（名人/冲突/数字/爆炸词）打分排序，输出 markdown 到 scripts/hotspots/。

用法:
  python daily_hotspot.py            # 抓今天的热点
  python daily_hotspot.py --top 5    # 只输出前 5 条
"""
import re
import sys
import io
import json
import html
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

SOURCES = [
    {"name": "网易国际", "url": "https://news.163.com/world/"},
    {"name": "新浪国际", "url": "https://news.sina.com.cn/world/"},
    {"name": "环球国际", "url": "https://world.huanqiu.com/"},
]

# 热度信号词（命中加分）
HOT_WORDS = [
    "特朗普", "拜登", "泽连斯基", "普京", "马斯克", "C罗", "梅西", "内马尔",
    "苹果", "OpenAI", "谷歌", "微软", "特斯拉", "英伟达", "美联储",
    "突发", "宣布", "曝光", "爆炸", "枪击", "地震", "暴跌", "暴涨", "破产",
    "离婚", "出轨", "怀孕", "去世", "夺冠", "决赛", "百万", "亿", "被",
    "称", "回应", "警告", "调查", "逮捕", "判刑",
]
# 排除词（军事/政治口水等用户不感兴趣的日常猎奇类过滤，可按需调整）
SKIP_WORDS = ["南海", "台海", "演习", "导弹", "防空", "航母", "外交部"]

HEADLINE_HOT_WORDS = ["百万", "亿", "C罗", "马斯克", "特朗普", "OpenAI", "突发", "曝光", "夺冠", "离婚", "去世"]


def fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            # 尝试多种编码
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [fetch fail] {url}: {e}")
        return ""


def extract_titles(html_text: str, source: str) -> list[str]:
    """从 HTML 提取 (标题, 分数) 列表，去重保序"""
    titles = []
    # 匹配 a 标签里的 title 属性 或 文本
    for m in re.finditer(r'<a[^>]+(?:title|aria-label)="([^"]{8,60})"[^>]*>', html_text):
        t = html.unescape(m.group(1)).strip()
        if t and len(t) >= 8 and not any(s in t for s in SKIP_WORDS):
            titles.append(t)
    for m in re.finditer(r'<a[^>]*>([^<]{8,60})</a>', html_text):
        t = html.unescape(m.group(1)).strip()
        if t and len(t) >= 8 and not any(s in t for s in SKIP_WORDS) and t not in titles:
            titles.append(t)
    # 去重
    seen = set()
    uniq = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def score(title: str) -> int:
    s = 0
    for w in HOT_WORDS:
        if w in title:
            s += 2
    for w in HEADLINE_HOT_WORDS:
        if w in title:
            s += 3
    # 数字加分（金钱/年龄/百分比）
    if re.search(r"\d", title):
        s += 1
    # 标点冲突感
    if any(c in title for c in "！？！"):
        s += 1
    return s


def main():
    top_n = None
    if "--top" in sys.argv:
        try:
            top_n = int(sys.argv[sys.argv.index("--top") + 1])
        except (IndexError, ValueError):
            top_n = None

    all_items = []
    for src in SOURCES:
        print(f"抓取 {src['name']}...")
        page = fetch(src["url"])
        if not page:
            continue
        for t in extract_titles(page, src["name"]):
            all_items.append({"title": t, "score": score(t), "source": src["name"]})

    # 按分数排序去重
    seen = set()
    ranked = []
    for it in sorted(all_items, key=lambda x: -x["score"]):
        if it["title"] not in seen:
            seen.add(it["title"])
            ranked.append(it)

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).parent / "hotspots"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{today}.md"

    lines = [f"# 国外实时热点 {today}", "", f"采集时间: {datetime.now().strftime('%H:%M')} | 共 {len(ranked)} 条", ""]
    lines.append("## 🔥 高热候选（分数≥6）")
    hot = [it for it in ranked if it["score"] >= 6]
    for it in hot[:15]:
        lines.append(f"- ⭐({it['score']}) [{it['source']}] {it['title']}")
    lines.append("")
    lines.append("## 📋 全部")
    for it in ranked[:40]:
        lines.append(f"- ({it['score']}) [{it['source']}] {it['title']}")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 已保存: {out_file}")

    # 输出高热候选（供 AI 会话读取）
    if hot:
        print("\n🔥 高热候选 TOP:")
        for it in hot[:top_n or 5]:
            print(f"  [{it['score']}] {it['title']}")

    # 写一个 JSON 供后续流程判断是否值得做
    json.dump({"date": today, "hot": hot[:10], "all": ranked[:40]},
              open(out_dir / f"{today}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
