"""
LLM Service — mock-first with optional real API integration.
Natural Language Intent Parsing lives in intent_parser.py (standalone).
"""

from __future__ import annotations

import os
from typing import Any

from intent_parser import (
    parse_natural_language_intent,
    CATEGORY_UI_MAP,
    CATEGORY_UI_REVERSE,
)

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")


def mock_llm_response(prompt: str, context: dict[str, Any] | None = None) -> str:
    ctx = context or {}
    task = ctx.get("task", "general")
    if task == "intent":
        return _mock_intent_summary(ctx)
    if task == "explanation":
        return _mock_explanation(ctx)
    if task == "follow_up":
        return _mock_follow_up(ctx)
    return f"[Mock LLM] Processed: {prompt[:80]}…"


def optional_llm_response(prompt: str, context: dict[str, Any] | None = None) -> str:
    if LLM_API_KEY and LLM_PROVIDER != "mock":
        return _call_real_llm(prompt, context)
    return mock_llm_response(prompt, context)


def _call_real_llm(prompt: str, context: dict[str, Any] | None) -> str:
    return mock_llm_response(prompt, context)


def parse_query_to_intent(
    query: str,
    budget: float | None = None,
    category: str = "General",
    preferences: list[str] | None = None,
    use_case_keys: list[str] | None = None,
    manual_override: bool = False,
    nl_parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge NL parse with manual widget values. Manual values take priority."""
    nl = nl_parsed or parse_natural_language_intent(query)

    if category and category != "General":
        cat_key = CATEGORY_UI_REVERSE.get(category, category.lower())
    else:
        cat_key = nl["parsed_category"]

    final_budget = budget if budget and budget > 0 else nl.get("parsed_budget")
    final_prefs = preferences if preferences is not None else nl.get("parsed_preferences", [])
    final_use_cases = use_case_keys if use_case_keys else nl.get("use_case_keys", [])

    if not final_use_cases:
        final_use_cases = ["general shopping"]

    return {
        "raw_query": query,
        "category": cat_key,
        "parsed_category": nl.get("parsed_category"),
        "parsed_category_ui": nl.get("parsed_category_ui"),
        "budget": final_budget,
        "parsed_budget": nl.get("parsed_budget"),
        "budget_min": final_budget * 0.85 if final_budget else None,
        "budget_max": final_budget * 1.15 if final_budget else None,
        "use_cases": final_use_cases,
        "parsed_use_case": nl.get("parsed_use_case", []),
        "preferences": final_prefs,
        "parsed_preferences": nl.get("parsed_preferences", []),
        "rule_hits": nl.get("rule_hits", []),
        "confidence": nl.get("confidence", 0.0),
        "manual_override": manual_override,
        "user_profile": _infer_profile(query),
        "summary": optional_llm_response(
            query,
            {
                "task": "intent",
                "query": query,
                "category": cat_key,
                "budget": final_budget,
                "manual_override": manual_override,
            },
        ),
    }


def generate_follow_up_questions(intent: dict[str, Any]) -> list[str]:
    questions = []
    if not intent.get("budget"):
        questions.append("您的预算区间大概是多少？这会影响推荐精度。")
    use_cases = intent.get("use_cases", [])
    if "gaming" in use_cases or "light gaming" in use_cases:
        questions.append("您主要玩哪些游戏？LOL/原神还是 3A 大作？")
    if intent.get("category") == "laptop":
        questions.append("开发栈主要是 Web/Python 还是移动端？内存需求不同。")
    if intent.get("category") == "phone":
        questions.append("是否在意生态系统（iOS / 鸿蒙 / 安卓）？")
    questions.append("对品牌有偏好吗？或者更看重性价比？")
    questions.append("是否需要考虑以旧换新或分期付款？")
    return questions[:4]


def _infer_profile(q: str) -> str:
    if "留学生" in q:
        return "Overseas student · coding + study"
    if "学生" in q:
        return "Student · budget-sensitive"
    if "商务" in q:
        return "Business user · brand & reliability"
    return "General online shopper"


def _mock_intent_summary(ctx: dict) -> str:
    cat = ctx.get("category", "general")
    budget = ctx.get("budget")
    b_str = f"约 ¥{int(budget)}" if budget else "未明确"
    override = "（含手动调整）" if ctx.get("manual_override") else ""
    return (
        f"识别品类：**{cat}** · 预算 **{b_str}**{override} · "
        f"已从自然语言解析结构化推荐条件。"
    )


def _mock_explanation(ctx: dict) -> str:
    name = ctx.get("product_name", "该商品")
    return f"**{name}** 在预算、评分和场景匹配上综合表现最优，详见下方分数拆解。"


def _mock_follow_up(ctx: dict) -> str:
    return "是否需要对比更多维度，或调整预算区间？"
