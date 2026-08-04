#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BGM 自动匹配混音（shipin-autopilot）
按赛道从本地 BGM 库选曲，混音到配音（音量低于人声），无缝循环补齐时长。

用法:
  python bgm_mix.py <人声final.wav> [--out out.wav] [--category 财经|体育|科技|社会|搞笑|默认]
  python bgm_mix.py 配音.wav --category 搞笑 --bgm 指定.mp3 --vol 0.15
"""
import sys
import io
import os
import json
import random
import argparse
import subprocess
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent.parent
BGM_DIR = Path(os.environ.get("BGM_DIR", r"E:\reasonix\money\MoneyPrinterTurbo\resource\songs"))

# 赛道 → 默认 BGM 文件名（可放自己的 BGM 库替换）
CATEGORY_BGM = {
    "财经": "output000.mp3",   # 沉稳
    "体育": "output001.mp3",   # 动感
    "科技": "output002.mp3",   # 未来感
    "社会": "output003.mp3",   # 中性
    "搞笑": "output004.mp3",   # 轻快
    "明星": "output005.mp3",   # 流行
    "默认": "output006.mp3",
}


def get_bgm(category: str, explicit: str = "") -> str:
    if explicit and os.path.exists(explicit):
        return explicit
    name = CATEGORY_BGM.get(category, CATEGORY_BGM["默认"])
    p = BGM_DIR / name
    if p.exists():
        return str(p)
    # 兜底：BGM 目录任意一个
    candidates = sorted(BGM_DIR.glob("*.mp3")) if BGM_DIR.exists() else []
    if candidates:
        return str(random.choice(candidates))
    print("❌ 未找到 BGM（设置 BGM_DIR 环境变量）")
    sys.exit(1)


def mix(voice: str, bgm: str, out: str, bgm_vol: float):
    """人声 + BGM（循环补时长，音量压低），输出混音 wav"""
    # 1) 获取人声时长
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                        "-of", "csv=p=0", voice], capture_output=True, text=True)
    dur = float(r.stdout.strip())

    # 2) ffmpeg 混音：BGM 循环到人声时长，音量 bgm_vol，人声音量 1.0
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-i", voice, "-i", bgm,
           "-filter_complex",
           f"[1:a]volume={bgm_vol},aloop=loop=-1:size=2e9,atrim=0:{dur}[bgm];"
           f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]",
           "-map", "[a]", "-ac", "1", "-ar", "24000", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if os.path.exists(out):
        return out
    print("❌ 混音失败:", r.stderr[-300:])
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("voice", help="人声配音 wav")
    parser.add_argument("--out", default="", help="输出路径")
    parser.add_argument("--category", default="默认", help="赛道：财经/体育/科技/社会/搞笑/明星/默认")
    parser.add_argument("--bgm", default="", help="指定 BGM 文件")
    parser.add_argument("--vol", type=float, default=0.15, help="BGM 音量（相对人声），默认 0.15")
    args = parser.parse_args()

    if not os.path.exists(args.voice):
        print(f"❌ 人声文件不存在: {args.voice}")
        sys.exit(1)

    bgm = get_bgm(args.category, args.bgm)
    print(f"🎵 赛道[{args.category}] BGM: {os.path.basename(bgm)} | 音量 {args.vol}")

    out = args.out or (Path(args.voice).with_name(Path(args.voice).stem + "_bgm.wav"))
    out = mix(args.voice, bgm, str(out), args.vol)
    print(f"✅ 混音完成: {out}")


if __name__ == "__main__":
    main()
