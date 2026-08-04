#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shipin 流水线 Step 4：按镜头组裁剪竖屏 + 拼接 + 混音 + 烧字幕。
用法: python pipeline_compose.py <镜头配置.json> <配音final.wav> <srt> <输出.mp4>
镜头配置 JSON: [{"src": "...", "start": 秒, "dur": 秒, "type": "P|R"}, ...]
"""
import sys, io, os, json, glob, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VF = ("scale=w='if(gt(a,1080/1920),-2,1080)':h='if(gt(a,1080/1920),1920,-2)':force_original_aspect_ratio=decrease,"
      "crop=1080:1920,setsar=1,fps=30,format=yuv420p")


def main():
    cfg_path, audio, srt, outv = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    groups = json.load(open(cfg_path, encoding="utf-8"))
    clip_dir = os.path.join(os.path.dirname(cfg_path), "clips_mix")
    os.makedirs(clip_dir, exist_ok=True)

    # 按配音时长缩放
    probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                            "-of", "csv=p=0", audio], capture_output=True, text=True)
    audio_dur = float(probe.stdout.strip())
    total = sum(g["dur"] for g in groups)
    scale = audio_dur / total
    print(f"音频 {audio_dur:.1f}s, 镜头原总长 {total:.1f}s, 缩放 {scale:.3f}")

    for i, g in enumerate(groups):
        out = os.path.join(clip_dir, f"clip{i:02d}.mp4")
        dur = g["dur"] * scale
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(g["start"]), "-t", str(dur),
                            "-i", g["src"], "-vf", VF, "-an", "-c:v", "libx264", "-crf", "20",
                            "-preset", "medium", out], capture_output=True, text=True)
        # 验证实际时长（素材不够长会截断）
        dd = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                             "-of", "csv=p=0", out], capture_output=True, text=True)
        actual = float(dd.stdout.strip())
        status = "OK" if actual >= dur * 0.95 else f"SHORT({actual:.1f}<{dur:.1f})"
        print(f"clip{i:02d} [{g.get('type','?')}] {status} {os.path.basename(g['src'])[:40]} @{g['start']}s")
        if status.startswith("SHORT"):
            print(f"  ⚠️ 素材不够长，换更长的素材再跑")

    # 拼接
    clips = sorted(glob.glob(os.path.join(clip_dir, "clip*.mp4")))
    concat_txt = os.path.join(clip_dir, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clips:
            f.write(f"file '{os.path.abspath(c)}'\n")
    combined = os.path.join(clip_dir, "silent_combined.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", concat_txt, "-c", "copy", combined], check=True)

    # 混音 + 烧字幕
    srt_esc = srt.replace("\\", "/").replace(":", "\\:")
    fc = (f"[0:v]subtitles='{srt_esc}':force_style="
          f"'FontName=Microsoft YaHei Bold,FontSize=14,PrimaryColour=&H00FFFFFF,"
          f"OutlineColour=&H00000000,BorderStyle=1,Outline=1.2'[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", combined, "-i", audio,
                    "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", outv], check=True)
    print(f"\n成片: {outv}")


if __name__ == "__main__":
    main()
