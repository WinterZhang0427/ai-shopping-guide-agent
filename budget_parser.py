"""
Budget range / cap parsing — standalone module for stable imports.
预算范围解析（独立模块，避免 intent_parser 同步不完整导致 ImportError）
"""

from __future__ import annotations

import re
from typing import Any


def _normalize_query_for_budget(query: str) -> str:
    return (
        query.replace("，", ",")
        .replace("－", "-")
        .replace("—", "-")
        .replace("～", "~")
    )


def convert_num(x: str, force_k: bool = False) -> float:
    """5k / 5 K / 8000 / 10000 → yuan amount."""
    s = str(x).strip().lower().replace(" ", "")
    if force_k or "k" in s:
        return float(re.sub(r"[kK]", "", s)) * 1000
    n = float(s)
    return n * 1000 if n < 100 else n


def parse_budget_range(query: str) -> dict[str, Any] | None:
    """
    Range-first budget parse. Returns min/max/parsed_budget (parsed = max).
    Patterns: 5k到7k, 8000-10000, 预算8000到10000
    """
    q = _normalize_query_for_budget(query)
    sep = r"(?:到|至|-|~|－)"
    range_patterns: list[tuple[str, bool]] = [
        (
            rf"预算\s*(\d+(?:\.\d+)?\s*[kK])\s*{sep}\s*(\d+(?:\.\d+)?\s*[kK])",
            True,
        ),
        (rf"预算\s*(\d{{3,6}})\s*{sep}\s*(\d{{3,6}})", False),
        (
            rf"(\d+(?:\.\d+)?\s*[kK])\s*{sep}\s*(\d+(?:\.\d+)?\s*[kK])",
            True,
        ),
        (rf"(\d{{3,6}})\s*{sep}\s*(\d{{3,6}})", False),
    ]
    for pattern, is_k in range_patterns:
        match = re.search(pattern, q, re.I)
        if match:
            low = convert_num(match.group(1), force_k=is_k)
            high = convert_num(match.group(2), force_k=is_k)
            lo, hi = min(low, high), max(low, high)
            return {
                "budget_min": lo,
                "budget_max": hi,
                "parsed_budget": hi,
                "budget_type": "range",
            }
    return None
