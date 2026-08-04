#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日热点合集 · 一键出片（shipin-autopilot）
整合全流程：热点采集 → LLM序号文案 → 真实素材抓取 → 配音 → 合成 → 输出。

用法:
  python daily_pipeline.py                       # 用最新热点出一版（云健配音）
  python daily_pipeline.py --date 2026-08-04     # 指定日期
  python daily_pipeline.py --voice yunjian|soda|bingtang   # 换配音
  python daily_pipeline.py --top 4 --no-material # 跳过素材抓取（用现有）

依赖: daily_hotspot.py / compile_daily.py / fetch_hotspot_materials.py / pipeline_tts.py / bgm_mix.py / pipeline_compose.py
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

BASE = Path(__file__).resolve().parent
SCRIPTS = BASE / "scripts"
HOTSPOTS = SCRIPTS / "hotspots"
RAW = BASE / "raw_materials"

VOICES = {
    "yunjian": {"name": "zh-CN-YunjianNeural", "provider": "edge", "label": "云健(edge·沉稳)"},
    "soda": {"name": "苏打", "provider": "mimo", "label": "苏打(小米·活力)"},
    "bingtang": {"name": "冰糖", "provider": "mimo", "label": "冰糖(小米·清亮)"},
}


def run(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, **kw)
        out = r.stdout.decode("utf-8", errors="replace")
        err = r.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"⚠️ 命令异常: {e}")
        return None
    if r.returncode != 0:
        print(f"⚠️ 命令失败: {' '.join(str(c) for c in cmd)[:120]}")
        print(err[-300:] if err else "")
    return r


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="")
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument("--voice", default="yunjian", choices=list(VOICES))
    parser.add_argument("--no-material", action="store_true", help="跳过素材抓取")
    parser.add_argument("--no-bgm", action="store_true")
    args = parser.parse_args()

    v = VOICES[args.voice]
    print(f"🎬 每日热点合集流水线 | 配音: {v['label']} | top {args.top}")

    # 1) 热点采集（若无今日热点）
    date = args.date
    if not date:
        jsons = sorted(glob.glob(str(HOTSPOTS / "*.json")))
        if jsons:
            date = Path(jsons[-1]).stem
    if not date:
        print("📡 采集热点...")
        run([sys.executable, str(SCRIPTS / "daily_hotspot.py")])
        jsons = sorted(glob.glob(str(HOTSPOTS / "*.json")))
        if not jsons:
            print("❌ 热点采集失败"); sys.exit(1)
        date = Path(jsons[-1]).stem
    print(f"📅 日期: {date}")

    # 2) 生成序号文案
    print("\n📝 生成 LLM 序号文案...")
    r = run([sys.executable, str(SCRIPTS / "compile_daily.py"), "--date", date, "--top", str(args.top)])
    script_file = HOTSPOTS / f"{date}_daily_script.txt"
    if not script_file.exists():
        print("❌ 文案生成失败"); sys.exit(1)

    # 3) 抓真实素材
    if not args.no_material:
        print("\n📹 抓取热点真实素材...")
        run([sys.executable, str(SCRIPTS / "fetch_hotspot_materials.py"), date, "--per-term", "3"])

    # 4) 配音
    print(f"\n🎙️ 配音({v['label']})...")
    tts_dir = RAW / f"daily_{args.voice}_tts"
    if v["provider"] == "edge":
        # edge-tts 逐句（需 MPT venv 的 python 有 edge_tts）
        py = r"E:\reasonix\money\MoneyPrinterTurbo\.venv\Scripts\python.exe"
        code = f"""
import asyncio, edge_tts, sys, io, os, json, wave, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
VOICE = "{v['name']}"
lines = [l.strip() for l in open(r"{script_file}", encoding="utf-8").read().split("\\n") if l.strip()]
os.makedirs(r"{tts_dir}", exist_ok=True)
async def gen():
    durs = []
    for i, line in enumerate(lines):
        wav = rf"{tts_dir}\\s{{i:02d}}.wav"
        if os.path.exists(wav) and os.path.getsize(wav) > 0:
            with wave.open(wav,"rb") as w: durs.append(w.getnframes()/w.getframerate())
            continue
        com = edge_tts.Communicate(line, VOICE, rate="+0%")
        await com.save(rf"{tts_dir}\\t{{i}}.mp3")
        subprocess.run(["ffmpeg","-y","-v","error","-i",rf"{tts_dir}\\t{{i}}.mp3","-ac","1","-ar","24000",wav], capture_output=True)
        os.remove(rf"{tts_dir}\\t{{i}}.mp3")
        with wave.open(wav,"rb") as w: durs.append(w.getnframes()/w.getframerate())
        print(f"OK {{i+1}}/{{len(lines)}}", flush=True)
    with wave.open(rf"{tts_dir}\\s00.wav","rb") as w0:
        nch,sw,fr = w0.getnchannels(), w0.getsampwidth(), w0.getframerate()
    out = r"{tts_dir}\\final.wav"
    with wave.open(out,"wb") as fo:
        fo.setnchannels(nch); fo.setsampwidth(sw); fo.setframerate(fr)
        for i in range(len(lines)):
            with wave.open(rf"{tts_dir}\\s{{i:02d}}.wav","rb") as w:
                fo.writeframes(w.readframes(w.getnframes()))
    json.dump({{"lines": lines, "durations": durs}}, open(r"{tts_dir}\\meta.json","w",encoding="utf-8"), ensure_ascii=False)
    print(f"done {{sum(durs):.1f}}s")
asyncio.run(gen())
"""
        r = run([py, "-c", code])
    else:
        r = run([sys.executable, str(SCRIPTS / "pipeline_tts.py"), str(script_file), str(tts_dir), v["name"]])
    final_audio = tts_dir / "final.wav"
    if not final_audio.exists():
        print("❌ 配音失败"); sys.exit(1)

    # 5) 生成字幕 + 镜头配置 + 合成
    print("\n🎞️ 生成字幕/镜头/合成...")
    out_name = f"每日热点合集_{date}_{args.voice}.mp4"
    out_path = Path(__file__).resolve().parent.parent / "output" / out_name
    shots_cfg = HOTSPOTS / f"daily_shots_{args.voice}.json"

    # 生成镜头配置（直接在本进程，避免嵌套转义）
    import wave as _wave
    meta = json.load(open(tts_dir / "meta.json", encoding="utf-8"))
    durs = meta["durations"]
    segs = [durs[0:4], durs[4:8], durs[8:12], durs[12:16], durs[16:18]]
    seg_durs = [sum(s) for s in segs]
    base = RAW / f"hotspot_{date}"
    shots = []
    for si, dur in enumerate(seg_durs):
        mats = sorted(glob.glob(str(base / f"seg{min(si+1,4)}" / "*.mp4")))
        if not mats:
            print(f"  ⚠️ seg{si+1} 无素材")
            continue
        per = dur / len(mats)
        for k, m in enumerate(mats):
            shots.append({"src": m, "start": 1, "dur": round(per, 1), "type": "R", "keyword": f"seg{si+1}"})
    shots_cfg.write_text(json.dumps(shots, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  ✅ 镜头配置 {len(shots)} 个")

    # 生成字幕
    srt_file = RAW / f"subtitle_daily_{args.voice}.srt"

    def _fmt(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = int(t % 60); ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    cur, parts = 0.0, []
    for i, (line, dur) in enumerate(zip(meta["lines"], durs)):
        parts.append(f"{i+1}\n{_fmt(cur)} --> {_fmt(cur+dur)}\n{line}\n")
        cur += dur
    srt_file.write_text("\n".join(parts), encoding="utf-8")
    print(f"  ✅ 字幕 {len(meta['lines'])} 条")

    # 合成
    compose_args = [sys.executable, str(SCRIPTS / "pipeline_compose.py"),
                    str(shots_cfg), str(final_audio), str(srt_file), str(out_path),
                    "--crf", "21"]
    if not args.no_bgm:
        compose_args += ["--bgm-category", "默认"]
    run(compose_args)

    if out_path.exists():
        print(f"\n✅ 每日合集完成: {out_path}")
    else:
        print("⚠️ 合成可能部分失败，检查输出")


if __name__ == "__main__":
    main()
