# -*- coding: utf-8 -*-
"""Shared retry/error classification helpers for LLM providers."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def safe_exception_text(exc: Exception) -> str:
    """Return an ASCII-safe exception string for robust logging."""
    return str(exc).encode("ascii", errors="backslashreplace").decode("ascii")


def clip_text(text: str, limit: int = 180) -> str:
    """Clip long text for concise logs."""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def is_ascii_encode_error(error: Any) -> bool:
    """Detect strict ASCII encode failures from exception or message."""
    msg = error if isinstance(error, str) else str(error)
    lower_msg = msg.lower()
    return (
        "ascii" in lower_msg
        and "codec can't encode" in lower_msg
        and "ordinal not in range(128)" in lower_msg
    )


def first_non_ascii_info(text: str) -> Optional[Tuple[int, str, str]]:
    """Return (index, char, codepoint_hex) for first non-ASCII char, else None."""
    for idx, ch in enumerate(text):
        if ord(ch) > 127:
            return idx, ch, f"U+{ord(ch):04X}"
    return None


def is_non_retryable_llm_error(exc: Exception) -> bool:
    """Return True when retry is unlikely to help (config/code/auth class errors)."""
    if isinstance(exc, (UnboundLocalError, NameError, SyntaxError)):
        return True

    message = safe_exception_text(exc).lower()
    non_retryable_signals = (
        "cannot access free variable",
        "contains non-ascii character at position",
        "api key not configured",
        "invalid api key",
        "incorrect api key",
        "authentication",
        "unauthorized",
        "permission denied",
        "forbidden",
        "401",
        "403",
    )
    return any(signal in message for signal in non_retryable_signals)
