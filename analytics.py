"""
Analytics — mock AB test metrics and tracking event design.
中文说明：Mock AB 实验 + 埋点方案，体现 PM 对转化漏斗和数据驱动的理解。
"""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

__all__ = [
    "get_tracking_events",
    "generate_mock_ab_test",
    "format_ab_table",
    "mock_ab_metrics",  # backward-compatible alias
]


# ---------------------------------------------------------------------------
# Tracking events (埋点设计)
# ---------------------------------------------------------------------------

def get_tracking_events() -> list[dict[str, str]]:
    """
    Define key tracking events for the shopping guide funnel.
    中文说明：定义导购漏斗核心埋点及其业务意义。
    """
    return [
        {
            "event": "exposure",
            "trigger": "用户进入导购页 / 推荐卡片曝光",
            "meaning": "衡量导购入口流量与曝光基数，AB 实验的分母",
            "key_fields": "user_id, session_id, page, variant(A/B), timestamp",
        },
        {
            "event": "search_query_submit",
            "trigger": "用户提交自然语言购物需求",
            "meaning": "衡量用户主动表达需求的意愿，反映 Query 质量",
            "key_fields": "query_text, category, budget, preferences, variant",
        },
        {
            "event": "recommendation_click",
            "trigger": "用户点击 Top 推荐商品卡片",
            "meaning": "核心 CTR 指标，衡量推荐 relevance",
            "key_fields": "product_id, rank, total_score, variant",
        },
        {
            "event": "add_to_cart",
            "trigger": "用户将推荐商品加入购物车",
            "meaning": "加购率，比 CTR 更接近 GMV 的前置指标",
            "key_fields": "product_id, price, source(recommendation/search), variant",
        },
        {
            "event": "product_compare",
            "trigger": "用户查看商品对比表",
            "meaning": "衡量决策深度，高对比率可能意味着推荐不够精准",
            "key_fields": "product_ids[], compare_duration_sec",
        },
        {
            "event": "recommendation_feedback",
            "trigger": "用户对推荐结果点赞/点踩",
            "meaning": "User Satisfaction 信号，用于 RLHF / 排序模型迭代",
            "key_fields": "feedback(positive/negative), product_id, reason",
        },
    ]


# ---------------------------------------------------------------------------
# Mock AB test
# ---------------------------------------------------------------------------

def generate_mock_ab_test(query: str, variant: str = "B") -> dict[str, Any]:
    """
    Generate deterministic mock AB metrics seeded by query hash.
    中文说明：基于 query hash 生成确定性 Mock AB 数据，便于 Demo 复现。

    Experiment:
      A = 传统关键词搜索结果
      B = AI 导购 Agent 推荐结果
    """
    seed = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)

    # Base metrics for control (A)
    base_ctr = 0.065 + (seed % 40) / 10000
    base_cart = base_ctr * 0.28
    base_cvr = base_cart * 0.35
    base_reform = 0.22 + (seed % 20) / 1000
    base_sat = 3.6 + (seed % 10) / 10

    # Treatment lift (B)
    lift_ctr = 1.35 + (seed % 20) / 100
    lift_cart = 1.42
    lift_cvr = 1.28
    lift_reform = 0.78  # lower is better
    lift_sat = 1.15

    a = {
        "variant": "A · 传统关键词搜索",
        "ctr": round(base_ctr, 4),
        "add_to_cart_rate": round(base_cart, 4),
        "conversion_rate": round(base_cvr, 4),
        "query_reformulation_rate": round(base_reform, 4),
        "user_satisfaction_score": round(base_sat, 2),
    }
    b = {
        "variant": "B · AI 导购 Agent",
        "ctr": round(base_ctr * lift_ctr, 4),
        "add_to_cart_rate": round(base_cart * lift_cart, 4),
        "conversion_rate": round(base_cvr * lift_cvr, 4),
        "query_reformulation_rate": round(base_reform * lift_reform, 4),
        "user_satisfaction_score": round(base_sat * lift_sat, 2),
    }

    return {
        "experiment_name": "AI Shopping Guide Agent vs Keyword Search",
        "hypothesis": "AI 导购 Agent 通过意图理解 + 可解释推荐，提升 CTR 和加购率，降低 Query 改写率",
        "duration_days": 14,
        "sample_size": 50000 + seed % 20000,
        "traffic_split": "50% / 50%",
        "control": a,
        "treatment": b,
        "lift": {
            "ctr": f"+{(lift_ctr - 1) * 100:.1f}%",
            "add_to_cart_rate": f"+{(lift_cart - 1) * 100:.1f}%",
            "conversion_rate": f"+{(lift_cvr - 1) * 100:.1f}%",
            "query_reformulation_rate": f"{(lift_reform - 1) * 100:.1f}%",
            "user_satisfaction_score": f"+{(lift_sat - 1) * 100:.1f}%",
        },
        "gmv_impact_estimate": f"+{18 + seed % 12}% GMV per session (estimated)",
        "notes": "Mock data for portfolio demo. Replace with real experiment platform data in production.",
    }


def format_ab_table(ab: dict[str, Any]) -> pd.DataFrame:
    """Format AB results as a comparison table."""
    metrics = ["ctr", "add_to_cart_rate", "conversion_rate",
               "query_reformulation_rate", "user_satisfaction_score"]
    labels = ["CTR", "加购率", "转化率", "Query 改写率", "用户满意度"]
    rows = []
    for m, label in zip(metrics, labels):
        rows.append({
            "指标": label,
            "A · 关键词搜索": ab["control"][m],
            "B · AI 导购": ab["treatment"][m],
            "Lift": ab["lift"].get(m.replace("add_to_cart_rate", "add_to_cart_rate")
                                   .replace("conversion_rate", "conversion_rate")
                                   .replace("query_reformulation_rate", "query_reformulation_rate")
                                   .replace("user_satisfaction_score", "user_satisfaction_score"), "-"),
        })
    # Fix lift keys
    lift_keys = ["ctr", "add_to_cart_rate", "conversion_rate",
                 "query_reformulation_rate", "user_satisfaction_score"]
    for i, lk in enumerate(lift_keys):
        rows[i]["Lift"] = ab["lift"][lk]
    return pd.DataFrame(rows)


# Backward-compatible alias (older app versions used this name)
mock_ab_metrics = generate_mock_ab_test
