"""
Recommender — multi-objective ranking with explainable score breakdown.
中文说明：多目标排序引擎，支持品类/预算/偏好/评分/销量/库存/利润综合打分。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from llm_service import generate_follow_up_questions, optional_llm_response
from intent_parser import (
    parse_natural_language_intent,
    CATEGORY_UI_MAP,
    CATEGORY_UI_REVERSE,
)
from budget_parser import parse_budget_range

try:
    from intent_parser import parse_user_intent as _parse_user_intent_impl
except ImportError:
    _parse_user_intent_impl = None

DATA_PATH = Path(__file__).parent / "products.csv"

__all__ = [
    "load_products",
    "parse_user_intent",
    "parse_natural_language_intent",
    "rank_products",
    "generate_recommendation_explanation",
    "build_comparison_table",
    "get_score_breakdown_df",
    "explain_non_recommendations",
    "filter_products",
    "score_product",
]

# Preference → tag keyword mapping for tag-match scoring
PREF_TAG_MAP: dict[str, tuple[str, ...]] = {
    "性价比": ("性价比", "低价"),
    "性能": ("性能", "编程", "游戏"),
    "轻便": ("轻薄", "便携", "轻便"),
    "续航": ("续航",),
    "品牌": ("品牌", "高端"),
    "评价": ("评分",),  # handled via rating column
    "低价": ("低价", "性价比"),
}

# Use-case → tag keyword mapping
USE_CASE_TAG_MAP: dict[str, tuple[str, ...]] = {
    "coding": ("编程", "性能", "办公"),
    "study": ("学生", "办公", "轻薄"),
    "gaming": ("游戏", "性能"),
    "light gaming": ("游戏", "性能"),
    "portability": ("轻薄", "便携"),
    "battery life": ("续航",),
    "commute": ("通勤", "降噪"),
    "photography": ("拍照", "影像"),
    "skincare": ("抗老", "保湿", "修复", "敏感肌"),
}


def load_products() -> pd.DataFrame:
    """Load product catalog from local CSV (RAG knowledge base)."""
    return pd.read_csv(DATA_PATH)


def parse_user_intent(
    query: str,
    budget: float | None = None,
    category: str | None = None,
    preferences: list[str] | None = None,
    manual_override: bool = False,
    nl_parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-export from intent_parser; inline fallback if symbol missing."""
    if _parse_user_intent_impl is not None:
        return _parse_user_intent_impl(
            query=query,
            budget=budget,
            category=category,
            preferences=preferences,
            manual_override=manual_override,
            nl_parsed=nl_parsed,
        )

    nl = nl_parsed if nl_parsed else parse_natural_language_intent(query)
    budget_range = parse_budget_range(query)
    if budget_range:
        nl_bmin = budget_range["budget_min"]
        nl_bmax = budget_range["budget_max"]
        nl_parsed_budget = budget_range["parsed_budget"]
    else:
        nl_bmin = nl.get("budget_min")
        nl_bmax = nl.get("budget_max")
        nl_parsed_budget = nl.get("parsed_budget")

    if category and category != "General":
        final_category = CATEGORY_UI_REVERSE.get(category, category.lower())
    else:
        final_category = nl.get("parsed_category", "general")

    final_preferences = preferences if preferences is not None else nl.get("parsed_preferences", [])

    if manual_override and budget is not None and budget > 0:
        final_bmax = float(budget)
        final_bmin = nl_bmin
        final_parsed = float(budget)
    elif nl_bmax is not None:
        final_bmin = nl_bmin
        final_bmax = nl_bmax
        final_parsed = nl_parsed_budget or nl_bmax
    elif budget is not None and budget > 0:
        final_bmin = None
        final_bmax = float(budget)
        final_parsed = float(budget)
    else:
        final_bmin = nl_bmin
        final_bmax = nl_bmax
        final_parsed = nl_parsed_budget

    if final_bmin and final_bmax:
        b_str = f"¥{int(final_bmin)} - ¥{int(final_bmax)}"
    elif final_bmax:
        b_str = f"约 ¥{int(final_bmax)}"
    else:
        b_str = "未明确"

    profile = "General online shopper"
    if "留学生" in query:
        profile = "Overseas student · coding + study"
    elif "学生" in query:
        profile = "Student · budget-sensitive"

    return {
        "raw_query": query,
        "category": final_category,
        "parsed_category": nl.get("parsed_category"),
        "parsed_category_ui": nl.get("parsed_category_ui", "General"),
        "budget": final_bmax,
        "parsed_budget": final_parsed,
        "budget_min": final_bmin,
        "budget_max": final_bmax,
        "use_cases": nl.get("use_case_keys", []) or ["general shopping"],
        "parsed_use_case": nl.get("parsed_use_case", []),
        "preferences": final_preferences,
        "parsed_preferences": nl.get("parsed_preferences", []),
        "rule_hits": nl.get("rule_hits", []),
        "confidence": nl.get("confidence", 0.0),
        "manual_override": manual_override,
        "user_profile": profile,
        "summary": (
            f"识别品类：**{final_category}** · 预算 **{b_str}**"
            f"{'（含手动调整）' if manual_override else ''} · "
            f"已从自然语言解析结构化推荐条件。"
        ),
    }


def _compute_budget_score(
    price: float,
    budget_min: float | None,
    budget_max: float | None,
) -> float:
    """
    Budget match score (0–100).
    区间内满分；低于下限仍可用较高分；超过上限显著降分。
    """
    if budget_max is None:
        return 70.0

    if price > budget_max * 1.15:
        return 0.0
    if price > budget_max:
        over_ratio = (price - budget_max) / budget_max
        return max(5.0, 35.0 - over_ratio * 150)

    if budget_min is not None:
        if budget_min <= price <= budget_max:
            return 100.0
        if price < budget_min:
            return 85.0

    # Single cap only (no min)
    if price <= budget_max:
        ratio = price / budget_max
        return max(40.0, 100.0 - abs(1.0 - ratio) * 60)
    return 0.0


def filter_products(intent: dict[str, Any], df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter by category; budget_max is hard upper limit.
    中文说明：品类过滤 + 价格 <= budget_max 硬性上限。
    """
    candidates = df.copy()
    cat = intent.get("category", "general")
    if cat and cat != "general":
        candidates = candidates[candidates["category"] == cat]

    bmax = intent.get("budget_max")
    if bmax:
        candidates = candidates[candidates["price"] <= bmax]

    return candidates.reset_index(drop=True)


def score_product(row: pd.Series, intent: dict[str, Any]) -> dict[str, float]:
    """
    Multi-objective score with per-dimension breakdown (0–100).
    中文说明：多目标打分，返回各维度分数供可解释推荐展示。

    Dimensions:
      - category_match, budget_match, rating_score, sales_score,
        preference_match, stock_score, profit_score
    """
    tags = str(row.get("tags", "")).lower()
    price = float(row["price"])
    budget_min = intent.get("budget_min")
    budget_max = intent.get("budget_max")

    # 1. Category match
    cat_match = 100.0 if row["category"] == intent.get("category") else 30.0

    # 2. Budget match — range-aware scoring
    budget_match = _compute_budget_score(price, budget_min, budget_max)

    # 3. Rating (scale 4.0–5.0 → 0–100)
    rating = float(row.get("rating", 4.5))
    rating_score = min(100.0, (rating - 4.0) / 1.0 * 100)

    # 4. Sales popularity (log-scaled)
    sales = float(row.get("sales", 1000))
    import math
    sales_score = min(100.0, math.log10(max(sales, 1)) / 5 * 100)

    # 5. Preference / use-case tag match
    pref_hits = 0
    pref_total = 0
    for pref in intent.get("preferences", []):
        pref_total += 1
        for kw in PREF_TAG_MAP.get(pref, (pref,)):
            if kw in tags:
                pref_hits += 1
                break
    for uc in intent.get("use_cases", []):
        pref_total += 1
        for kw in USE_CASE_TAG_MAP.get(uc, (uc,)):
            if kw in tags:
                pref_hits += 1
                break
    preference_match = (pref_hits / pref_total * 100) if pref_total else 60.0

    # 6. Stock availability
    stock = float(row.get("stock", 0))
    stock_score = min(100.0, stock / 10)  # 1000 stock → 100

    # 7. Profit score (platform GMV optimization signal)
    profit = float(row.get("profit_score", 0.5))
    profit_score = profit * 100

    # Weighted total — adjustable for AB experiments
    weights = {
        "category_score": 0.15,
        "budget_score": 0.20,
        "rating_score": 0.15,
        "sales_score": 0.10,
        "preference_score": 0.25,
        "stock_score": 0.05,
        "profit_score": 0.10,
    }
    breakdown = {
        "category_score": round(cat_match, 1),
        "budget_score": round(budget_match, 1),
        "rating_score": round(rating_score, 1),
        "sales_score": round(sales_score, 1),
        "preference_score": round(preference_match, 1),
        "stock_score": round(stock_score, 1),
        "profit_score": round(profit_score, 1),
    }
    total = sum(breakdown[k] * weights[k] for k in weights)
    breakdown["final_score"] = round(total, 1)
    breakdown["weights"] = weights
    # backward-compatible aliases
    breakdown["total_score"] = breakdown["final_score"]
    return breakdown


def rank_products(intent: dict[str, Any], df: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Full pipeline: filter → score → sort descending.
    中文说明：召回 → 打分 → 排序，返回带分数拆解的 DataFrame。
    """
    if df is None:
        df = load_products()
    cat = intent.get("category", "general")
    bmax = intent.get("budget_max")

    candidates = filter_products(intent, df)
    if candidates.empty and cat and cat != "general":
        cat_df = df[df["category"] == cat].copy()
        if bmax:
            cat_df = cat_df[cat_df["price"] <= bmax]
        candidates = cat_df.reset_index(drop=True)
    if candidates.empty and bmax:
        candidates = df[df["price"] <= bmax].reset_index(drop=True)
    if candidates.empty and cat and cat != "general":
        candidates = df[df["category"] == cat].reset_index(drop=True)
    if candidates.empty:
        candidates = df.copy()

    scores = [score_product(row, intent) for _, row in candidates.iterrows()]
    scored = candidates.copy()
    for key in scores[0]:
        if key != "weights":
            scored[key] = [s[key] for s in scores]

    return scored.sort_values("final_score", ascending=False).reset_index(drop=True)


def generate_recommendation_explanation(
    intent: dict[str, Any], top_products: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """
    Generate structured explanation per Top-N product.
    中文说明：为每个 Top 商品生成「为什么推荐 / 风险 / 适合人群」。
    """
    explanations = []
    for i, p in enumerate(top_products, 1):
        price = float(p.get("price", 0))
        bmin, bmax = intent.get("budget_min"), intent.get("budget_max") or intent.get("budget")
        budget_ok = ""
        if bmin and bmax:
            if bmin <= price <= bmax:
                budget_ok = f"价格在预算区间 ¥{int(bmin):,}-¥{int(bmax):,} 内"
            elif price < bmin:
                budget_ok = f"低于区间下限，但仍在 ¥{int(bmax):,} 上限内"
            else:
                budget_ok = f"略超预算上限 ¥{int(bmax):,}"
        elif bmax:
            diff = price - bmax
            budget_ok = "符合预算" if price <= bmax else f"略超预算 ¥{diff:.0f}"

        why = (
            f"{budget_ok}；评分 {p.get('rating', '-')} / 销量 {p.get('sales', 0):,}；"
            f"标签匹配度高（{p.get('tags', '')}）；库存 {p.get('stock', 0)} 件充足"
        )
        risks = _identify_risks(p, intent)
        audience = _identify_audience(p, intent)

        explanations.append({
            "rank": f"Top {i}",
            "product_name": p["product_name"],
            "why": why,
            "risks": risks,
            "audience": audience,
            "llm_summary": optional_llm_response(
                f"Explain {p['product_name']}",
                {"task": "explanation", "product_name": p["product_name"]},
            ),
        })
    return explanations


def build_comparison_table(top: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side comparison for Top-N products."""
    cols = ["product_name", "brand", "price", "rating", "sales", "tags", "stock", "final_score"]
    labels = ["商品", "品牌", "价格(¥)", "评分", "销量", "标签", "库存", "综合分"]
    out = top[cols].copy()
    out.columns = labels
    return out


def get_score_breakdown_df(product: dict[str, Any]) -> pd.DataFrame:
    """Format score breakdown as a display-ready DataFrame."""
    dims = [
        ("category_score", "category_score · 品类匹配", 0.15),
        ("budget_score", "budget_score · 预算匹配", 0.20),
        ("rating_score", "rating_score · 用户评分", 0.15),
        ("sales_score", "sales_score · 销量热度", 0.10),
        ("preference_score", "preference_score · 偏好匹配", 0.25),
        ("stock_score", "stock_score · 库存充足", 0.05),
        ("profit_score", "profit_score · 平台利润", 0.10),
    ]
    rows = []
    for key, label, weight in dims:
        val = product.get(key, product.get(key.replace("_score", "_match"), 0))
        rows.append({
            "Score Dimension": label,
            "Score": val,
            "Weight": f"{weight:.0%}",
            "Weighted": round(float(val) * weight, 2),
        })
    final = product.get("final_score", product.get("total_score", 0))
    rows.append({
        "Score Dimension": "final_score · 综合得分",
        "Score": final,
        "Weight": "100%",
        "Weighted": final,
    })
    return pd.DataFrame(rows)


def explain_non_recommendations(
    ranked: pd.DataFrame,
    intent: dict[str, Any],
    top_n: int = 3,
    max_items: int = 5,
) -> list[dict[str, Any]]:
    """
    Explain why certain products did NOT rank in Top N.
    中文说明：解释未进 Top 推荐的原因，体现可解释排序的产品价值。
    """
    if len(ranked) <= top_n:
        return []

    top_score = float(ranked.iloc[0]["final_score"])
    results = []
    for _, row in ranked.iloc[top_n : top_n + max_items].iterrows():
        reasons: list[str] = []
        price = float(row["price"])
        bmax = intent.get("budget_max") or intent.get("budget")
        bmin = intent.get("budget_min")

        if bmax and price > bmax:
            reasons.append(f"超预算：¥{price:,.0f} 高于预算上限 ¥{int(bmax):,}")
        elif bmin and bmax and price < bmin:
            reasons.append(f"低于预算下限：¥{price:,.0f}（目标区间 ¥{int(bmin):,}-¥{int(bmax):,}）")

        rating = float(row.get("rating", 0))
        if rating < 4.6:
            reasons.append(f"评分偏低：{rating}（Top 推荐普遍 ≥ 4.7）")

        stock = int(row.get("stock", 0))
        if stock < 200:
            reasons.append(f"库存不足：仅 {stock} 件，存在缺货风险")

        pref = float(row.get("preference_score", 60))
        if pref < 45:
            reasons.append("与偏好/场景标签匹配度低（preference_score < 45）")

        budget_sc = float(row.get("budget_score", 70))
        if budget_sc < 50:
            reasons.append("预算匹配分过低，性价比感知弱")

        gap = top_score - float(row["final_score"])
        results.append({
            "product_name": row["product_name"],
            "final_score": float(row["final_score"]),
            "score_gap_vs_top1": round(gap, 1),
            "reasons": reasons if reasons else ["综合得分低于 Top 3，多维度加权后排名靠后"],
        })
    return results


def _identify_risks(p: dict, intent: dict) -> str:
    risks = []
    if "游戏" not in str(p.get("tags", "")) and "gaming" in str(intent.get("use_cases")):
        risks.append("游戏性能不是最强")
    cap = intent.get("budget_max") or intent.get("budget")
    if cap and p.get("price", 0) > cap:
        risks.append("价格略超预算")
    if p.get("stock", 0) < 200:
        risks.append("库存偏紧，可能缺货")
    return "；".join(risks) if risks else "暂无明显风险"


def _identify_audience(p: dict, intent: dict) -> str:
    tags = str(p.get("tags", ""))
    if "学生" in tags:
        return "学生、预算敏感用户"
    if "商务" in tags or "品牌" in tags:
        return "商务用户、品牌偏好者"
    if "通勤" in tags:
        return "通勤族、差旅用户"
    return "通用消费者、轻决策用户"


# ---------------------------------------------------------------------------
# Budget parse sanity checks (intent_parser._extract_budget_with_rules)
# Run: py -3 -c "from intent_parser import parse_natural_language_intent as p; ..."
#
# | query              | budget_min | budget_max | parsed_budget |
# |--------------------|------------|------------|---------------|
# | 预算8000到10000    | 8000       | 10000      | 10000         |
# | 预算5000到7000     | 5000       | 7000       | 7000          |
# | 预算 5000 到 7000  | 5000       | 7000       | 7000          |
# | 5000-7000          | 5000       | 7000       | 7000          |
# | 5k到7k             | 5000       | 7000       | 7000          |
# | 不超过8000         | None       | 8000       | 8000          |
# | 一万以内           | None       | 10000      | 10000         |
#
# User scenario: 拍照好续航强手机，预算5000到7000 → phones ≤7000 in Top 3
# ---------------------------------------------------------------------------
