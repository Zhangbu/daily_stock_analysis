# -*- coding: utf-8 -*-
"""LLM response style helpers (runtime prompt modifiers)."""

from __future__ import annotations

from typing import Dict

DEFAULT_RESPONSE_STYLE = "normal"
SUPPORTED_RESPONSE_STYLES = {
    "normal",
    "caveman_lite",
    "caveman_full",
    "caveman_ultra",
}

_STYLE_INSTRUCTIONS: Dict[str, str] = {
    "caveman_lite": (
        "Use concise writing. Remove filler and repetition. "
        "Prefer short direct sentences while keeping key evidence."
    ),
    "caveman_full": (
        "Use very concise writing. Keep only essential facts, decisions, and risks. "
        "Prefer short phrases over long sentences."
    ),
    "caveman_ultra": (
        "Use ultra-concise writing. Telegraphic style is allowed. "
        "Output only critical information and action items."
    ),
}


def normalize_response_style(value: str | None) -> str:
    """Normalize raw response style from env/config."""
    raw = (value or "").strip().lower()
    if raw in SUPPORTED_RESPONSE_STYLES:
        return raw
    return DEFAULT_RESPONSE_STYLE


def build_style_instruction(style: str, structured_json: bool = False) -> str:
    """Build style instruction snippet for prompt suffix."""
    normalized = normalize_response_style(style)
    if normalized == DEFAULT_RESPONSE_STYLE:
        return ""

    base = _STYLE_INSTRUCTIONS.get(normalized, "")
    if not base:
        return ""

    if structured_json:
        guard = (
            "Keep all required JSON fields and schema constraints unchanged. "
            "Only shorten wording inside free-text values."
        )
    else:
        guard = "Preserve factual accuracy and risk visibility."

    return f"\n\n## Response Style\n- Mode: {normalized}\n- {base}\n- {guard}"


def apply_response_style(prompt: str, style: str, structured_json: bool = False) -> str:
    """Append style instruction when a non-default style is enabled."""
    suffix = build_style_instruction(style=style, structured_json=structured_json)
    if not suffix:
        return prompt
    return prompt + suffix
