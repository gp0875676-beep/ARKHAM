# utils/markdown.py — Telegram MarkdownV1/V2 escape helpers.
"""Escape user-supplied strings so they never break Telegram Markdown."""
from __future__ import annotations

_MD_V1_SPECIAL = "_*`["
_MD_V2_SPECIAL = "_*[]()~`>#+-=|{}.!"


def escape_markdown(text: str, version: int = 1) -> str:
    """Escape special Markdown characters. version=1 (legacy) or 2 (V2)."""
    if text is None:
        return ""
    chars = _MD_V2_SPECIAL if version == 2 else _MD_V1_SPECIAL
    return "".join("\\" + ch if ch in chars else ch for ch in text)


def truncate(text: str, limit: int = 4000) -> str:
    """Telegram message hard cap is 4096; leave headroom."""
    if text is None:
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"
