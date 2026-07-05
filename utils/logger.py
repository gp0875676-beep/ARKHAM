# utils/logger.py — loguru-based structured logger with safe defaults.
"""Shared logger. Configured once at import time."""
from __future__ import annotations

import sys

from loguru import logger as _logger

from config import get_settings

_cfg = get_settings()

_logger.remove()
_logger.add(
 sys.stderr,
 level=_cfg.log_level.upper(),
 format=(
 "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
 "<level>{level: <8}</level> | "
 "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
 "<level>{message}</level>"
    ),
 backtrace=True,
 diagnose=False,
)


def get_logger(name: str):
 return _logger.bind(name=name)
