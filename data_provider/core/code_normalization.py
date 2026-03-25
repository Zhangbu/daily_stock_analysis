# -*- coding: utf-8 -*-
"""Stock code normalization helpers."""


def normalize_stock_code(stock_code: str) -> str:
    """Normalize stock code by stripping exchange prefixes/suffixes."""
    code = stock_code.strip()
    upper = code.upper()

    if upper.startswith(("SH", "SZ")) and not upper.startswith("SH.") and not upper.startswith("SZ."):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    if "." in code:
        base, suffix = code.rsplit(".", 1)
        if suffix.upper() in ("SH", "SZ", "SS") and base.isdigit():
            return base

    return code


def canonical_stock_code(code: str) -> str:
    """Return the canonical uppercase form of a stock code."""
    return (code or "").strip().upper()
