#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shipin 短视频流水线：一键执行 Step 2 配音（小米 MiMo TTS 逐句生成 + 拼接 + 生成 srt）。
用法: python pipeline_tts.py <script.txt> <输出目录> [音色,默认冰糖]
"""
import sys, io, os, json, base64, urllib.request, wave

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

MIMO_URL = "https://api.xiaomimimo.com/v1/chat/completions"
# 从环境变量读取，勿硬编码密钥
try:
    from config import TTSConfig
    MIMO_KEY = TTSConfig.MIMO_KEY
    MIMO_URL = TTSConfig.MIMO_URL
    VOICE = sys.argv[3] if len(sys.argv) > 3 else TTSConfig.DEFAULT_VOICE
    STYLE = TTSConfig.STYLE
    TTSConfig.require_key()
except ImportError:
    MIMO_KEY = os.environ.get("MIMO_API_KEY", "")
    VOICE = sys.argv[3] if len(sys.argv) > 3 else "冰糖"
    STYLE = "用清晰、自然、适合短视频旁白的语气朗读，语速适中，抑扬顿挫，有讲故事的感觉。"
    if not MIMO_KEY:
        print("⚠️ 请设置环境变量 MIMO_API_KEY（小米 MiMo 平台 API key）")
        sys.exit(1)


def tts(text: str) -> bytes | None:
    payload = {
        "model": "mimo-v2.5-tts",
        "messages": [
            {"role": "user", "content": STYLE},
            {"role": "assistant", "content": text},
        ],
        "audio": {"format": "wav", "voice": VOICE},
    }
    req = urllib.request.Request(
        MIMO_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": MIMO_KEY, "Content-Type": "application/json"},
    )
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=120))
        audio = resp["choices"][0]["message"].get("audio")
        if audio and audio.get("data"):
            return base64.b64decode(audio["data"])
        print("无音频:", json.dumps(resp, ensure_ascii=False)[:200])
    except Exception as e:
        print("ERR:", str(e)[:150])
    return None


def main():
    script_path, out_dir = sys.argv[1], sys.argv[2]
    lines = [l.strip() for l in open(script_path, encoding="utf-8").read().split("\n") if l.strip()]
    os.makedirs(out_dir, exist_ok=True)

    durations, wavs = [], []
    for i, line in enumerate(lines):
        data = tts(line)
        if not data:
            print(f"FAIL {i+1}/{len(lines)}: {line[:20]}")
            continue
        p = os.path.join(out_dir, f"s{i:02d}.wav")
        open(p, "wb").write(data)
        with wave.open(p, "rb") as w:
            durations.append(w.getnframes() / w.getframerate())
        wavs.append(p)
        print(f"OK {i+1:2d}/{len(lines)} ({durations[-1]:.2f}s): {line[:22]}")

    # 拼接
    final = os.path.join(out_dir, "final.wav")
    with wave.open(wavs[0], "rb") as w0:
        nch, sw, fr = w0.getnchannels(), w0.getsampwidth(), w0.getframerate()
    with wave.open(final, "wb") as out:
        out.setnchannels(nch); out.setsampwidth(sw); out.setframerate(fr)
        for p in wavs:
            with wave.open(p, "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))

    # 生成 srt
    def fmt(t):
        h, m = int(t // 3600), int(t % 3600 // 60)
        s, ms = int(t % 60), int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    cur, srt_parts = 0.0, []
    for i, (line, dur) in enumerate(zip(lines, durations)):
        srt_parts.append(f"{i+1}\n{fmt(cur)} --> {fmt(cur+dur)}\n{line}\n")
        cur += dur
    srt_path = os.path.join(os.path.dirname(out_dir.rstrip("/\\")), "subtitle_mimo.srt")
    open(srt_path, "w", encoding="utf-8").write("\n".join(srt_parts))

    print(f"\n完成: 配音 {final} ({sum(durations):.1f}s) | 字幕 {srt_path} ({len(lines)} 条)")


if __name__ == "__main__":
    main()
