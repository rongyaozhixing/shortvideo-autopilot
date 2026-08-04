#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一配置模块（shipin-autopilot）
- 支持 .env 文件 + 环境变量
- 按模块分组（tts/素材/api/发布/复盘）
- 密钥不落盘，全部从环境读取；缺失时给出明确提示
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    """加载项目根目录 .env（若存在）"""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


_load_dotenv()


def _get(key: str, default: str = "", required: bool = False, hint: str = "") -> str:
    val = os.environ.get(key, default)
    if required and not val:
        print(f"❌ 缺少必需配置: {key} {hint}")
        sys.exit(1)
    return val


class TTSConfig:
    """配音配置（小米 MiMo，可扩展多服务商）"""
    PROVIDER = _get("TTS_PROVIDER", "mimo")
    MIMO_URL = _get("MIMO_URL", "https://api.xiaomimimo.com/v1/chat/completions")
    MIMO_KEY = _get("MIMO_API_KEY", "", hint="（小米 MiMo 平台获取: platform.xiaomimimo.com）")
    MIMO_MODEL = _get("MIMO_MODEL", "mimo-v2.5-tts")
    DEFAULT_VOICE = _get("TTS_DEFAULT_VOICE", "冰糖")
    STYLE = _get("TTS_STYLE", "用清晰、自然、适合短视频旁白的语气朗读，语速适中，抑扬顿挫，有讲故事的感觉。")
    # 备用服务商（未配置则跳过）
    OPENAI_KEY = _get("OPENAI_API_KEY", "")
    OPENAI_BASE = _get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_VOICE = _get("OPENAI_TTS_VOICE", "alloy")

    @classmethod
    def require_key(cls):
        if not cls.MIMO_KEY:
            print("❌ 缺少必需配置: MIMO_API_KEY（小米 MiMo 平台获取: platform.xiaomimimo.com）")
            sys.exit(1)


class ImageConfig:
    """封面生图配置（agnes 优先，备用可扩展）"""
    AGNES_BASE = _get("AGNES_BASE_URL", "https://api.agnes-ai.cn/v1")
    AGNES_KEY = _get("AGNES_API_KEY", "")
    AGNES_MODEL = _get("AGNES_IMAGE_MODEL", "agnes-image-2.1-flash")


class VisionConfig:
    """识图配置（agnes 优先，本地 Ollama 备用）"""
    AGNES_VISION_MODEL = _get("AGNES_VISION_MODEL", "agnes-2.5-flash")
    OLLAMA_URL = _get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
    OLLAMA_MODEL = _get("OLLAMA_MODEL", "qwen2.5vl:7b")


class HotspotConfig:
    """热点采集配置"""
    SOURCES = [s.strip() for s in _get(
        "HOTSPOT_SOURCES",
        "https://news.163.com/world/,https://news.sina.com.cn/world/,https://world.huanqiu.com/",
    ).split(",") if s.strip()]
    SCORE_THRESHOLD = int(_get("HOTSPOT_SCORE_THRESHOLD", "6"))
    MAX_ITEMS = int(_get("HOTSPOT_MAX_ITEMS", "40"))


class PublishConfig:
    """发布配置"""
    DOUYIN_URL = _get("DOUYIN_PUBLISH_URL", "https://creator.douyin.com/creator-micro/content/upload")
    ACCOUNT = _get("DOUYIN_ACCOUNT", "")


def print_config_status():
    """启动时打印配置状态，便于排查"""
    status = {
        "TTS.MIMO": "✅" if TTSConfig.MIMO_KEY else "❌ 缺 MIMO_API_KEY",
        "TTS.OPENAI备用": "✅" if TTSConfig.OPENAI_KEY else "未配置",
        "Image.AGNES": "✅" if ImageConfig.AGNES_KEY else "⚠️ 未配置（封面将用视频帧）",
        "Vision.OLLAMA": "✅" if VisionConfig.OLLAMA_URL else "未配置",
        "Hotspot.SOURCES": f"{len(HotspotConfig.SOURCES)} 个源",
    }
    print("📋 配置状态:")
    for k, v in status.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    print_config_status()
