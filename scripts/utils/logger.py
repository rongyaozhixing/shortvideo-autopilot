#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统一日志模块：分级日志 + 落盘 + 控制台输出
用法:
  from utils.logger import get_logger
  log = get_logger("hotspot")
  log.info("..."); log.error("...")
日志写入 <项目根>/logs/<名称>.log，控制台同步输出。
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

# 项目根 = 本文件上两级（utils/logger.py -> 根）
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

_LEVEL = getattr(logging, "LOG_LEVEL", "INFO")
if isinstance(_LEVEL, str):
    _LEVEL = getattr(logging, _LEVEL.upper(), logging.INFO)

_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def get_logger(name: str = "app") -> logging.Logger:
    """获取带文件+控制台输出的 logger"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 已初始化
        return logger
    logger.setLevel(_LEVEL)

    # 控制台 handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(sh)

    # 文件 handler（按天轮转：logs/<name>-YYYYMMDD.log）
    day = datetime.now().strftime("%Y%m%d")
    fh = logging.FileHandler(LOG_DIR / f"{name}-{day}.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(_FMT))
    logger.addHandler(fh)

    logger.propagate = False
    return logger


def log_dir() -> Path:
    return LOG_DIR
