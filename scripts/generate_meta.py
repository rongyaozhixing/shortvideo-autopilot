#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 智能标题/标签生成（shipin-autopilot）
读视频文案 → 调用 LLM（agnes）→ 生成 3 套差异化标题 + 精准标签组合。

用法:
  python generate_meta.py <文案.md|txt> [--title 初拟标题] [--out out.json]
输出:
  - 3 套标题（数字+冲突+名人 / 提问式 / 悬念式）
  - 标签组合（名人 + 泛流量 + 垂直）
  - 一句话推荐理由
"""
import sys
import io
import os
import json
import argparse
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

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
        return "⚠️ 未配置 AGNES_API_KEY，跳过 AI 生成"
    payload = {
        "model": LLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
    }
    req = urllib.request.Request(
        LLM_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=120))
        msg = resp["choices"][0]["message"]
        # 纯文本任务：最终答案在 content（reasoning_content 是思考过程）
        # 识图任务（多模态）才是 reasoning_content 有答案 —— 见 agnes 记忆
        return msg.get("content") or msg.get("reasoning_content") or ""
    except Exception as e:
        return f"⚠️ LLM 调用失败: {e}"


PROMPT = """你是短视频运营专家。根据下面的视频文案，生成发布物料：

【文案】
{script}

请严格输出 JSON（不要其他文字）：
{{
  "titles": ["标题1：数字+冲突+名人/热词+悬念", "标题2：提问式引发站队", "标题3：口语悬念式"],
  "topics": ["#名人话题", "#泛流量话题", "#垂直话题", "#蹭热点话题", "#吃瓜/搞笑等情绪话题"],
  "recommend": "推荐标题：xxx。理由：一句话"
}}
要求：
- 标题 ≤30 字，口语化，有冲突或悬念，避免标题党到违规
- 话题 5-8 个，覆盖名人/泛流量/垂直三类
- 基于文案实际内容，不编造
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("script", help="文案文件路径")
    parser.add_argument("--title", default="", help="初拟标题（作参考）")
    parser.add_argument("--out", default="", help="输出 json 路径")
    args = parser.parse_args()

    script = Path(args.script)
    if not script.exists():
        print(f"❌ 文件不存在: {args.script}")
        sys.exit(1)
    text = script.read_text(encoding="utf-8")
    if args.title:
        text += f"\n（初拟标题：{args.title}）"

    print("🤖 调用 LLM 生成标题/标签...")
    result = call_llm(PROMPT.format(script=text[:3000]))

    # 尝试解析 JSON
    meta = None
    try:
        # 去掉 markdown 围栏
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        meta = json.loads(clean)
    except Exception:
        meta = None

    # 兜底：从任意文本里挖出 { ... } JSON 块
    if not meta:
        import re
        m = re.search(r"\{[^{}]*\"titles\"[^{}]*\}", result, re.S)
        if not m:
            m = re.search(r"\{[\s\S]*\}", result)
        if m:
            try:
                meta = json.loads(m.group(0))
            except Exception:
                meta = None

    if meta:
        print("\n📝 生成结果:")
        for i, t in enumerate(meta.get("titles", []), 1):
            print(f"  标题{i}: {t}")
        print(f"  话题: {' '.join(meta.get('topics', []))}")
        print(f"  推荐: {meta.get('recommend', '')}")
        if args.out:
            Path(args.out).write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"\n✅ 已保存: {args.out}")
    else:
        print("\n⚠️ 未解析出 JSON，原始输出：")
        print(result[:800])


if __name__ == "__main__":
    main()
