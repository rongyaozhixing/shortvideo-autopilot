#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""热点真实素材抓取（shipin-autopilot）
按 compile_daily 生成的素材搜索词，从 Pexels/Pixabay 搜视频下载到本地。

用法:
  python fetch_hotspot_materials.py <date> [--min-dur 10] [--per-term 1]
读取: scripts/hotspots/<date>_daily_meta.json 的 segments[].material_terms
输出: raw_materials/hotspot_<date>/*.mp4（按热点分目录）
"""
import sys
import io
import os
import json
import glob
import argparse
import urllib.request
import urllib.parse
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
HOTSPOTS = BASE / "hotspots"


def load_api_key():
    """从 ~/.media_apis.json 读 Pexels key"""
    home = Path.home() / ".media_apis.json"
    if home.exists():
        try:
            d = json.load(open(home, encoding="utf-8"))
            return d.get("pexels", {}).get("key", "")
        except Exception:
            pass
    return os.environ.get("PEXELS_API_KEY", "")


def search_pexels(key: str, term: str, per_page: int = 5) -> list[dict]:
    """Pexels 搜视频，返回 [{id, url, duration, width, height}]"""
    url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": term, "per_page": per_page, "orientation": "portrait"})
    req = urllib.request.Request(url, headers={
        "Authorization": key,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=30))
        items = []
        for v in resp.get("videos", []):
            # 取第一个可用文件
            files = v.get("video_files", [])
            f = next((x for x in files if x.get("height") and x["height"] >= 720), files[0] if files else None)
            if f:
                items.append({"id": v.get("id"), "url": f.get("link"), "duration": v.get("duration", 0),
                              "width": f.get("width", 0), "height": f.get("height", 0)})
        return items
    except Exception as e:
        print(f"  Pexels 搜索失败 {term}: {e}")
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="日期 YYYY-MM-DD")
    parser.add_argument("--min-dur", type=float, default=10, help="最小素材时长")
    parser.add_argument("--per-term", type=int, default=1, help="每词下载几个")
    args = parser.parse_args()

    meta_file = HOTSPOTS / f"{args.date}_daily_meta.json"
    if not meta_file.exists():
        print(f"❌ 无 {meta_file}（先跑 compile_daily.py）"); sys.exit(1)
    meta = json.load(open(meta_file, encoding="utf-8"))

    key = load_api_key()
    if not key:
        print("❌ 无 Pexels key（~/.media_apis.json 或 PEXELS_API_KEY）"); sys.exit(1)

    out_root = Path(__file__).resolve().parent.parent / "raw_materials" / f"hotspot_{args.date}"
    out_root.mkdir(parents=True, exist_ok=True)

    for si, seg in enumerate(meta.get("segments", [])):
        terms = seg.get("material_terms", [])
        seg_dir = out_root / f"seg{si+1}"
        seg_dir.mkdir(exist_ok=True)
        print(f"\n📹 热点{si+1}: {seg.get('hotspot','')[:30]} | 搜索词: {terms}")
        got = 0
        for term in terms:
            items = search_pexels(key, term, per_page=5)
            for it in items:
                if it["duration"] < args.min_dur:
                    continue
                out = seg_dir / f"{term[:12]}_{it['id']}.mp4"
                if out.exists():
                    continue
                try:
                    req = urllib.request.Request(it["url"], headers={"User-Agent": "Mozilla/5.0"})
                    data = urllib.request.urlopen(req, timeout=60).read()
                    out.write_bytes(data)
                    print(f"  ✅ [{it['duration']}s {it['width']}x{it['height']}] {out.name}")
                    got += 1
                    if got >= args.per_term:
                        break
                except Exception as e:
                    print(f"  ⚠️ 下载失败 {it['id']}: {e}")
            if got >= args.per_term:
                break
        if got == 0:
            print(f"  ⚠️ 未找到可用素材（{terms}）")


if __name__ == "__main__":
    main()
