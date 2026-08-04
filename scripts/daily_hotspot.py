#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国外实时热点采集（增强版）
- 多数据源：网易国际/新浪国际/环球国际（可配置）
- 敏感词过滤：自动剔除违规/冲突过激新闻，规避审核拦截
- 赛道分类：财经/体育/社会/科技
- 热度权重：关键词打分 + 时长衰减（可选）
- 输出 markdown + json 到 scripts/hotspots/

用法:
  python daily_hotspot.py                # 抓今天热点
  python daily_hotspot.py --top 5        # 只输出前 5
  python daily_hotspot.py --categories    # 按赛道分组输出
"""
import re
import sys
import io
import json
import html
import argparse
import urllib.request
from datetime import datetime, date
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# 项目内导入
sys.path.insert(0, str(Path(__file__).resolve().parent))
from utils.logger import get_logger
try:
    from config import HotspotConfig
except Exception:
    HotspotConfig = None

log = get_logger("hotspot")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

DEFAULT_SOURCES = [
    {"name": "网易国际", "url": "https://news.163.com/world/"},
    {"name": "新浪国际", "url": "https://news.sina.com.cn/world/"},
    {"name": "环球国际", "url": "https://world.huanqiu.com/"},
]

# ---------- 赛道分类 ----------
CATEGORY_RULES = {
    "财经": ["美联储", "油价", "股市", "股价", "美元", "通胀", "降息", "加息", "财报", "市值", "营收", "亿", "破产", "收购", "IPO", "经济", "汇率", "银行", "关税", "贸易", "芯片", "半导体", "AI", "OpenAI", "谷歌", "苹果", "微软", "特斯拉", "英伟达"],
    "体育": ["C罗", "梅西", "内马尔", "世界杯", "欧冠", "英超", "皇马", "巴萨", "NBA", "进球", "夺冠", "决赛", "足球", "球衣", "转会", "金球奖", "奥运"],
    "科技": ["AI", "OpenAI", "谷歌", "苹果", "微软", "特斯拉", "英伟达", "芯片", "半导体", "机器人", "大模型", "算法", "5G", "量子", "太空", "火箭", "卫星", "发布", "系统"],
    "社会": ["曝光", "离婚", "出轨", "去世", "地震", "枪击", "爆炸", "怀孕", "逮捕", "判刑", "调查", "难民", "移民", "疫情", "病毒", "洪水", "火灾", "遇难", "失踪", "结婚", "女", "男", "孩子", "家庭"],
    "明星": ["C罗", "梅西", "内马尔", "贝克汉姆", "金卡戴珊", "比伯", "泰勒", "爱泼斯坦", "奥斯卡", "格莱美", "好莱坞"],
}

# ---------- 敏感词过滤（规避审核拦截） ----------
SENSITIVE_WORDS = [
    "南海", "台海", "台湾", "新疆", "西藏", "香港", "钓鱼岛", "黄岩岛", "藏独", "疆独",
    "演习", "导弹", "防空", "航母", "核武", "核弹", "战争", "开战", "军事行动", "斩首",
    "屠杀", "恐怖袭击", "恐怖分子", "圣战", "人质", "斩首行动", "处决",
    "性侵", "强奸", "恋童", "儿童色情",
]

# ---------- 热度信号词 ----------
HOT_WORDS = [
    "特朗普", "拜登", "泽连斯基", "普京", "马斯克", "C罗", "梅西", "内马尔",
    "苹果", "OpenAI", "谷歌", "微软", "特斯拉", "英伟达", "美联储",
    "突发", "宣布", "曝光", "爆炸", "枪击", "地震", "暴跌", "暴涨", "破产",
    "离婚", "出轨", "怀孕", "去世", "夺冠", "决赛", "百万", "亿", "被",
    "称", "回应", "警告", "调查", "逮捕", "判刑",
]
HEADLINE_HOT_WORDS = ["百万", "亿", "C罗", "马斯克", "特朗普", "OpenAI", "突发", "曝光", "夺冠", "离婚", "去世"]


def fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        log.warning(f"抓取失败 {url}: {e}")
        return ""


def extract_titles(html_text: str) -> list[str]:
    titles = []
    for m in re.finditer(r'<a[^>]+(?:title|aria-label)="([^"]{8,60})"[^>]*>', html_text):
        t = html.unescape(m.group(1)).strip()
        if t and len(t) >= 8:
            titles.append(t)
    for m in re.finditer(r'<a[^>]*>([^<]{8,60})</a>', html_text):
        t = html.unescape(m.group(1)).strip()
        if t and len(t) >= 8 and t not in titles:
            titles.append(t)
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
    if re.search(r"\d", title):
        s += 1
    if any(c in title for c in "！？！"):
        s += 1
    return s


def classify(title: str) -> str:
    """赛道分类：返回匹配度最高的赛道"""
    best, best_score = "综合", 0
    for cat, words in CATEGORY_RULES.items():
        cnt = sum(1 for w in words if w in title)
        if cnt > best_score:
            best, best_score = cat, cnt
    return best if best_score > 0 else "综合"


def is_sensitive(title: str) -> bool:
    return any(w in title for w in SENSITIVE_WORDS)


def generate_draft(title: str, category: str) -> str:
    """按赛道/钩子模板生成文案初稿（每行一句，可直接喂 TTS）"""
    hooks = {
        "财经": f"刚发生的这件事，直接影响了全世界人的钱包。\n{title}。\n很多人的第一反应是：这跟我有什么关系？\n但接下来这几分钟，请认真看完。",
        "体育": f"先别划走，体育圈今天爆了个大新闻。\n{title}。\n这事传开后，评论区直接吵翻了。\n支持的和反对的，谁都说服不了谁。",
        "科技": f"又一个改变生活的科技新闻来了。\n{title}。\n很多人还没意识到，这件事将影响我们未来几年的日常。\n今天给你讲清楚。",
        "社会": f"今天全网都在讨论这件事。\n{title}。\n有人看完沉默了，有人看完坐不住了。\n你怎么看？评论区聊聊。",
        "明星": f"娱乐圈又出大事了。\n{title}。\n消息一出，热搜直接炸了。\n这背后的故事，比你想的复杂。",
        "综合": f"先别划走，今天有个热点必须说。\n{title}。\n这事传开的速度，快得超乎想象。\n看完你也会有自己的判断。",
    }
    draft = hooks.get(category, hooks["综合"])
    draft += "\n关注我，下一条更精彩。"
    return draft


def main():
    parser = argparse.ArgumentParser(description="国外实时热点采集")
    parser.add_argument("--top", type=int, help="只输出前 N 条高热候选")
    parser.add_argument("--categories", action="store_true", help="按赛道分组输出")
    parser.add_argument("--draft", action="store_true", help="同时生成文案初稿")
    args = parser.parse_args()

    sources = DEFAULT_SOURCES
    if HotspotConfig:
        custom = HotspotConfig.SOURCES
        if len(custom) >= 3:
            sources = [{"name": f"源{i+1}", "url": u} for i, u in enumerate(custom)]

    all_items = []
    for src in sources:
        log.info(f"抓取 {src['name']}...")
        page = fetch(src["url"])
        if not page:
            continue
        for t in extract_titles(page):
            if is_sensitive(t):
                log.debug(f"过滤敏感: {t[:30]}")
                continue
            all_items.append({
                "title": t,
                "score": score(t),
                "category": classify(t),
                "source": src["name"],
            })

    seen, ranked = set(), []
    for it in sorted(all_items, key=lambda x: -x["score"]):
        if it["title"] not in seen:
            seen.add(it["title"])
            ranked.append(it)

    today = datetime.now().strftime("%Y-%m-%d")
    out_dir = Path(__file__).resolve().parent / "hotspots"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{today}.md"
    threshold = HotspotConfig.SCORE_THRESHOLD if HotspotConfig else 6

    lines = [f"# 国外实时热点 {today}", "",
             f"采集时间: {datetime.now().strftime('%H:%M')} | 共 {len(ranked)} 条 | 高热阈值 ≥{threshold}", ""]
    hot = [it for it in ranked if it["score"] >= threshold]

    lines.append("## 🔥 高热候选")
    for it in hot[:15]:
        lines.append(f"- ⭐({it['score']}) [{it['category']}|{it['source']}] {it['title']}")

    if args.categories:
        lines.append("")
        lines.append("## 📂 按赛道")
        for cat in ["财经", "科技", "体育", "社会", "明星", "综合"]:
            items = [it for it in ranked if it["category"] == cat]
            if items:
                lines.append(f"\n### {cat}")
                for it in items[:8]:
                    lines.append(f"- ({it['score']}) {it['title']}")

    lines.append("")
    lines.append("## 📋 全部")
    for it in ranked[:HotspotConfig.MAX_ITEMS if HotspotConfig else 40]:
        lines.append(f"- ({it['score']}) [{it['category']}] [{it['source']}] {it['title']}")

    out_file.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"已保存: {out_file}")

    # 文案初稿
    drafts = {}
    if args.draft:
        for it in hot[:5]:
            drafts[it["title"]] = generate_draft(it["title"], it["category"])
        draft_file = out_dir / f"{today}_drafts.json"
        json.dump(drafts, open(draft_file, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log.info(f"文案初稿: {draft_file} ({len(drafts)} 条)")

    json.dump({"date": today, "hot": hot[:10], "all": ranked[:40]},
              open(out_dir / f"{today}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n🔥 高热候选 TOP:")
    for it in hot[: args.top or 5]:
        print(f"  [{it['score']}][{it['category']}] {it['title']}")


if __name__ == "__main__":
    main()
