#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""素材智能匹配引擎（shipin-autopilot）
1. 扫描本地素材库（Pexels 缓存 + 自定义目录）→ 建索引（时长/分辨率/来源/关键词）
2. 输入文案关键词 → 自动生成镜头配置 JSON（免手写）

用法:
  python build_material_index.py --scan [目录...]      # 扫描建索引
  python build_material_index.py --match "钱,少年,足球" --dur 131.7   # 按关键词出镜头JSON
  python build_material_index.py --index 素材索引.json --match ...     # 用已有索引
"""
import sys
import io
import os
import json
import glob
import argparse
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = BASE / "scripts" / "material_index.json"

# 素材关键词 → 中文语义标签（用于按文案词匹配）
TAG_MAP = {
    "钱": ["money", "cash", "dollar", "bill", "finance", "rich"],
    "足球": ["soccer", "football", "stadium", "ball", "goal"],
    "少年": ["teen", "boy", "youth", "kid", "child", "young"],
    "家庭": ["family", "home", "parent", "father", "son", "dad"],
    "比赛": ["match", "game", "competition", "sports", "player"],
    "奖杯": ["trophy", "award", "champion", "prize", "winner"],
    "训练": ["training", "practice", "gym", "workout", "coach"],
    "情绪": ["angry", "happy", "sad", "excited", "crying", "shout"],
    "城市": ["city", "street", "building", "urban", "traffic"],
    "自然": ["nature", "mountain", "beach", "sea", "forest", "sky"],
    "生活": ["daily", "life", "routine", "school", "dorm", "room"],
    "科技": ["tech", "computer", "phone", "screen", "robot", "ai"],
}


def probe_video(path: str) -> dict:
    """用 ffprobe 取时长/分辨率"""
    try:
        r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                            "-show_streams", "-show_format", path], capture_output=True, text=True, timeout=30)
        info = json.loads(r.stdout)
        vs = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
        dur = float(info.get("format", {}).get("duration", 0))
        w, h = (vs[0].get("width", 0), vs[0].get("height", 0)) if vs else (0, 0)
        return {"duration": round(dur, 1), "width": w, "height": h}
    except Exception:
        return {"duration": 0, "width": 0, "height": 0}


def scan(dir_path: str) -> list[dict]:
    items = []
    for ext in ("*.mp4", "*.mov", "*.webm", "*.mkv"):
        for f in glob.glob(os.path.join(dir_path, ext)):
            info = probe_video(f)
            items.append({
                "path": os.path.abspath(f),
                "file": os.path.basename(f),
                "duration": info["duration"],
                "width": info["width"],
                "height": info["height"],
                "src": "pexels" if "cache_videos" in f else "custom",
                "tags": [],
            })
    return items


def guess_tags(filename: str, src: str) -> list[str]:
    """按文件名猜标签（Pexels 缓存按素材记录，这里先用文件名启发式）"""
    tags = []
    low = filename.lower()
    for tag, keys in TAG_MAP.items():
        if any(k in low for k in keys):
            tags.append(tag)
    if src == "pexels":
        tags.append("pexels")
    return tags


def match_to_shots(index: list[dict], keywords: str, total_dur: float) -> list[dict]:
    """按关键词把素材匹配成镜头配置（按比例分配时长）"""
    words = [w.strip() for w in keywords.split(",") if w.strip()]
    shots = []
    used = set()
    if not words:
        words = ["生活"]
    n = len(words)
    base = total_dur / n
    for i, word in enumerate(words):
        # 找匹配素材（含关键词标签或路径关键字）
        candidates = []
        for item in index:
            if item["path"] in used:
                continue
            low_path = (item["file"] + " " + " ".join(item["tags"])).lower()
            if word.lower() in low_path or any(word in t for t in item["tags"]):
                candidates.append(item)
        if not candidates:
            candidates = [it for it in index if it["path"] not in used]
        if not candidates:
            break
        # 选时长最接近的
        chosen = min(candidates, key=lambda it: abs(it["duration"] - base))
        used.add(chosen["path"])
        shots.append({
            "src": chosen["path"],
            "start": 2,  # 从 2s 起剪（避开片头）
            "dur": round(base, 1),
            "type": "P" if chosen["src"] == "pexels" else "R",
            "keyword": word,
        })
    return shots


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scan", nargs="*", default=[], help="扫描的素材目录")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="索引 json 路径")
    parser.add_argument("--match", default="", help="关键词（逗号分隔）")
    parser.add_argument("--dur", type=float, default=60.0, help="目标总时长")
    args = parser.parse_args()

    if args.scan:
        all_items = []
        for d in args.scan:
            print(f"扫描 {d}...")
            items = scan(d)
            for it in items:
                it["tags"] = guess_tags(it["file"], it["src"])
            all_items.extend(items)
        Path(args.index).write_text(json.dumps(all_items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 索引 {len(all_items)} 个素材 -> {args.index}")
        return

    if args.match:
        if not os.path.exists(args.index):
            print(f"❌ 索引不存在: {args.index}（先 --scan 建索引）")
            sys.exit(1)
        index = json.load(open(args.index, encoding="utf-8"))
        shots = match_to_shots(index, args.match, args.dur)
        out = Path(args.index).parent / "shots_auto.json"
        out.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✅ 生成 {len(shots)} 个镜头 -> {out}")
        for s in shots:
            print(f"  [{s['type']}] {s['keyword']}: {os.path.basename(s['src'])[:40]} ({s['dur']}s)")


if __name__ == "__main__":
    main()
