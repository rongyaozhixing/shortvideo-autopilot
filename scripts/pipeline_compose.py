#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shipin 流水线 Step 4：按镜头组裁剪竖屏 + 拼接 + 混音 + 烧字幕。
用法: python pipeline_compose.py <镜头配置.json> <配音final.wav> <srt> <输出.mp4>
      python pipeline_compose.py <cfg> <audio> <srt> <out> --crf 23 --bgm-category 搞笑 --batch
镜头配置 JSON: [{"src": "...", "start": 秒, "dur": 秒, "type": "P|R"}, ...]

参数:
  --crf 18-28        编码质量（18 高清 / 23 均衡 / 28 省体积）；抖音竖屏建议 crf 20-23
  --preset fast|medium  编码速度
  --bgm-category 赛道  混入 BGM（财经/体育/科技/社会/搞笑/明星/默认）
  --batch N          批量合成 N 个版本（随机打乱镜头顺序，供复盘择优）
"""
import sys, io, os, json, glob, subprocess, argparse, random

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

VF = ("scale=w='if(gt(a,1080/1920),-2,1080)':h='if(gt(a,1080/1920),1920,-2)':force_original_aspect_ratio=decrease,"
      "crop=1080:1920,setsar=1,fps=30,format=yuv420p")

# 抖音竖屏推荐：1080x1920, 30fps, H.264 crf 20-23, aac 192k
DOUYIN_CRF = 21


def add_bgm(audio: str, category: str, out_audio: str):
    """调 bgm_mix.py 混入 BGM"""
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bgm_mix.py")
    r = subprocess.run([sys.executable, script, audio, "--category", category, "--out", out_audio],
                       capture_output=True, text=True)
    return out_audio if os.path.exists(out_audio) else audio


def compose(groups, audio, srt, outv, crf, preset, bgm_category=""):
    clip_dir = os.path.join(os.path.dirname(os.path.abspath(outv)), "clips_mix")
    os.makedirs(clip_dir, exist_ok=True)

    # 按配音时长缩放
    probe = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                            "-of", "csv=p=0", audio], capture_output=True, text=True)
    audio_dur = float(probe.stdout.strip())
    total = sum(g["dur"] for g in groups)
    scale = audio_dur / total
    print(f"音频 {audio_dur:.1f}s, 镜头原总长 {total:.1f}s, 缩放 {scale:.3f}")

    # 清理旧 clip
    for old in glob.glob(os.path.join(clip_dir, "clip*.mp4")):
        os.remove(old)

    for i, g in enumerate(groups):
        out = os.path.join(clip_dir, f"clip{i:02d}.mp4")
        dur = g["dur"] * scale
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(g["start"]), "-t", str(dur),
                            "-i", g["src"], "-vf", VF, "-an", "-c:v", "libx264", "-crf", str(crf),
                            "-preset", preset, out], capture_output=True, text=True)
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

    # BGM 混音（可选）
    mix_audio = audio
    if bgm_category:
        mix_audio = add_bgm(audio, bgm_category, os.path.join(clip_dir, "voice_bgm.wav"))
        print(f"🎵 BGM[{bgm_category}] 已混入")

    # 混音 + 烧字幕
    srt_esc = srt.replace("\\", "/").replace(":", "\\:")
    fc = (f"[0:v]subtitles='{srt_esc}':force_style="
          f"'FontName=Microsoft YaHei Bold,FontSize=14,PrimaryColour=&H00FFFFFF,"
          f"OutlineColour=&H00000000,BorderStyle=1,Outline=1.2'[v]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", combined, "-i", mix_audio,
                    "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
                    "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
                    "-c:a", "aac", "-b:a", "192k", "-shortest", outv], check=True)
    print(f"\n成片: {outv}")
    return outv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cfg", help="镜头配置 json")
    parser.add_argument("audio", help="配音 wav")
    parser.add_argument("srt", help="字幕 srt")
    parser.add_argument("out", help="输出 mp4")
    parser.add_argument("--crf", type=int, default=DOUYIN_CRF, help="编码质量 18-28")
    parser.add_argument("--preset", default="medium", choices=["fast", "medium", "slow"])
    parser.add_argument("--bgm-category", default="", help="BGM 赛道")
    parser.add_argument("--batch", type=int, default=0, help="批量生成 N 版本")
    args = parser.parse_args()

    groups = json.load(open(args.cfg, encoding="utf-8"))
    print(f"📹 crf={args.crf}（抖音推荐 20-23）preset={args.preset}")

    if args.batch > 1:
        # 批量：打乱镜头顺序生成多版本
        for v in range(args.batch):
            shuffled = list(groups)
            if v > 0:
                random.shuffle(shuffled)
            outv = args.out.replace(".mp4", f"_v{v+1}.mp4")
            compose(shuffled, args.audio, args.srt, outv, args.crf, args.preset, args.bgm_category)
        print(f"\n🎬 批量完成 {args.batch} 个版本（供复盘择优）")
    else:
        compose(groups, args.audio, args.srt, args.out, args.crf, args.preset, args.bgm_category)


if __name__ == "__main__":
    main()
