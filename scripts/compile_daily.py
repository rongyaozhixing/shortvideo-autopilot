#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日热点合集脚本生成 v2（shipin-autopilot）
一条视频装多个当天热点，每个热点：
  - 独特文案（无模板重复）+ 个人看法 + 互动
  - 生成素材搜索关键词（供抓真实素材）

用法:
  python compile_daily.py                      # 读今天热点，LLM 生成合集
  python compile_daily.py --top 5 --dry        # 只打印不写文件
  python compile_daily.py --date 2026-08-04
输出:
  scripts/hotspots/<date>_daily_script.txt    # 每行一句（直喂 TTS）
  scripts/hotspots/<date>_daily_meta.json     # 标题/话题/每段素材关键词
"""
import sys
import io
import os
import json
import glob
import argparse
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
HOTSPOTS = BASE / "hotspots"

LLM_URL = "https://api.agnes-ai.cn/v1/chat/completions"
LLM_MODEL = "agnes-2.5-flash"


def load_key():
    key = os.environ.get("AGNES_API_KEY", "")
    if not key:
        home = Path.home() / ".agnes.json"
        if home.exists():
            try:
                key = json.load(open(home, encoding="utf-8"))["api_key"]
            except Exception:
                pass
    return key


def call_llm(prompt: str) -> str:
    key = load_key()
    if not key:
        return "⚠️ 未配置 AGNES_API_KEY"
    payload = {"model": LLM_MODEL, "messages": [{"role": "user", "content": prompt}], "max_tokens": 2500}
    req = urllib.request.Request(
        LLM_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=180))
        msg = resp["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""
    except Exception as e:
        return f"⚠️ LLM 失败: {e}"


# 让 LLM 为每个热点生成：独特文案（叙述为主 + 序号过渡）+ 素材搜索关键词
GENERATE_PROMPT = """你是短视频主编，做一条"今日国外热点速览"合集视频（约2分钟，装{total}个热点，每个约25-30秒）。

今天的热点：
{hotlist}

要求：
1. 每个热点写一段 ~50-70 字的口语文案（每句一行），**以叙述为主**：一句讲清事件 + 一两句补充关键信息或背景。可以自然带出观点/点评，但**不要每段都问观众问题**——互动提问最多在 1-2 段出现，其余纯叙述。
2. **每个热点段开头用序号过渡**："第一"、"第二"、"第三"……（口语自然，如"第一件，""第二件，"）。
3. 每段之间自然衔接，避免模板感。
4. 结尾一段：一句总结 + 一句互动提问 + 关注引导。
5. 每个热点给 2 个中文素材搜索词（用于找真实视频画面，如"OpenAI发布会""伊朗军事""国际足联""石油钻井"），要具体、能搜到真实素材。

严格输出 JSON（不要其他文字）：
{{
  "segments": [
    {{"hotspot": "热点标题", "script": ["句1", "句2", "句3"], "material_terms": ["搜索词1", "搜索词2"]}}
  ],
  "ending": ["结尾句1", "结尾句2"],
  "title": "合集标题（≤30字，有冲突感）",
  "topics": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"]
}}
"""


def parse_json(text: str):
    import re
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(clean)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


# ---------- 去重：已做热点记录 ----------
DONE_FILE = HOTSPOTS / "done_hotspots.json"


def normalize_title(t: str) -> str:
    """标题规范化：去标点空格，用于去重比对"""
    import re
    return re.sub(r"[\s\W]+", "", t)


def load_done() -> set:
    if DONE_FILE.exists():
        try:
            return set(json.load(open(DONE_FILE, encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_done(done: set):
    DONE_FILE.write_text(json.dumps(sorted(done), ensure_ascii=False, indent=1), encoding="utf-8")


def run_daily_hotspot():
    """重新采集热点"""
    import subprocess
    subprocess.run([sys.executable, str(BASE / "daily_hotspot.py")], capture_output=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="")
    parser.add_argument("--top", type=int, default=4)
    parser.add_argument("--dry", action="store_true", help="只打印不写文件")
    parser.add_argument("--allow-repeat", action="store_true", help="允许重复热点（跳过去重）")
    args = parser.parse_args()

    date = args.date
    if not date:
        jsons = sorted(glob.glob(str(HOTSPOTS / "*.json")))
        if not jsons:
            print("❌ 无热点，先跑 daily_hotspot.py"); sys.exit(1)
        date = Path(jsons[-1]).stem
    data_file = HOTSPOTS / f"{date}.json"
    if not data_file.exists():
        print(f"❌ 无 {data_file}"); sys.exit(1)

    # 时效检查：只接受当天或前一天（--date 指定时跳过）
    if not args.date:
        from datetime import datetime, timedelta
        try:
            d = datetime.strptime(date, "%Y-%m-%d").date()
            today = datetime.now().date()
            if (today - d).days > 1:
                print(f"⚠️ 热点 {date} 已超过 1 天，重新采集最新热点...")
                run_daily_hotspot()
                jsons = sorted(glob.glob(str(HOTSPOTS / "*.json")))
                if jsons:
                    date = Path(jsons[-1]).stem
                    data_file = HOTSPOTS / f"{date}.json"
        except ValueError:
            pass

    data = json.load(open(data_file, encoding="utf-8"))
    hot = data.get("hot", data.get("all", []))
    if not hot:
        print("❌ 热点为空"); sys.exit(1)

    # 去重：排除已做过的热点（除非 --allow-repeat）
    if not args.allow_repeat:
        done = load_done()
        before = len(hot)
        hot = [h for h in hot if normalize_title(h["title"]) not in done]
        print(f"🔄 去重: {before} -> {len(hot)}（已做过 {before - len(hot)} 条）")
        if not hot:
            print("❌ 今天的热点都做过了，建议 --allow-repeat 或扩大 top"); sys.exit(1)

    hot = hot[: args.top]
    hotlist = "\n".join(f"{i+1}. {h['title']}" for i, h in enumerate(hot))
    print(f"🤖 LLM 生成合集文案（{len(hot)} 个热点）...")
    result = call_llm(GENERATE_PROMPT.format(total=len(hot), hotlist=hotlist))
    meta = parse_json(result)
    if not meta:
        print("❌ 无法解析 LLM 输出：")
        print(result[:800]); sys.exit(1)

    # 组装脚本
    all_lines = []
    for i, seg in enumerate(meta.get("segments", [])):
        for line in seg.get("script", []):
            all_lines.append(line.strip())
    all_lines.extend(meta.get("ending", []))

    if args.dry:
        print("\n".join(all_lines))
        print("\n标题:", meta.get("title"))
        print("话题:", " ".join(meta.get("topics", [])))
        for seg in meta.get("segments", []):
            print(f"  素材[{seg.get('hotspot','')[:20]}]: {seg.get('material_terms')}")
        return

    script_path = HOTSPOTS / f"{date}_daily_script.txt"
    script_path.write_text("\n".join(all_lines), encoding="utf-8")

    meta_out = {
        "date": date,
        "hotspots": [{"title": h["title"], "category": h.get("category", "")} for h in hot],
        "title": meta.get("title", ""),
        "topics": meta.get("topics", []),
        "segments": [{"hotspot": s.get("hotspot", ""), "material_terms": s.get("material_terms", [])}
                     for s in meta.get("segments", [])],
        "script_file": str(script_path),
    }
    meta_path = HOTSPOTS / f"{date}_daily_meta.json"
    meta_path.write_text(json.dumps(meta_out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 记录已做热点（去重）
    done = load_done()
    for h in hot:
        done.add(normalize_title(h["title"]))
    save_done(done)
    print(f"✅ 已记录 {len(hot)} 个热点到去重库（累计 {len(done)} 条）")

    print(f"📰 每日热点合集（{date} · {len(hot)} 个热点）")
    print(f"🏷️ 标题: {meta.get('title')}")
    print(f"  话题: {' '.join(meta.get('topics', []))}")
    print(f"\n📝 脚本: {script_path}（{len(all_lines)} 句）")
    print("\n--- 每段预览 ---")
    for seg in meta.get("segments", []):
        print(f"[{seg.get('hotspot','')[:24]}]")
        for line in seg.get("script", []):
            print(f"  {line}")
        print(f"  素材词: {seg.get('material_terms')}")


if __name__ == "__main__":
    main()
