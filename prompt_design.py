"""
Prompt Design — Agent prompt template construction.
中文说明：展示 Agent 如何组装 Prompt，便于 PM 面试讲解 Prompt Engineering。
"""

from __future__ import annotations

from typing import Any


def build_prompt_design(
    intent: dict[str, Any],
    retrieved_products: list[dict[str, Any]],
) -> dict[str, Any]:
    """Construct the prompt template used by the Shopping Guide Agent."""
    business_rules = [
        "仅推荐 retrieved_products 中的真实 SKU，禁止编造参数",
        "Top 3 必须包含：推荐理由、适合人群、潜在风险",
        "预算偏差 > 15% 的商品需标注「略超预算」",
        "preference_score 权重 25%，优先满足用户显式偏好",
        "profit_score 权重 10%，平衡用户体验与平台 GMV",
        "库存 < 200 的商品降低推荐优先级",
    ]

    output_format = {
        "intent_summary": "string — 用户需求一句话总结",
        "top_recommendations": [
            {
                "rank": 1,
                "product_id": "string",
                "why_recommend": "string",
                "risk": "string",
                "target_user": "string",
            }
        ],
        "follow_up_questions": ["string"],
        "score_breakdown": "object — 7-dimension scores per product",
    }

    product_snippets = [
        f"- {p.get('product_name', p.get('name', ''))} | ¥{p.get('price')} | "
        f"rating {p.get('rating')} | tags: {p.get('tags', '')}"
        for p in retrieved_products[:5]
    ]

    user_need = {
        "raw_query": intent.get("raw_query", ""),
        "category": intent.get("category", ""),
        "budget": intent.get("budget"),
        "use_cases": intent.get("use_cases", []),
        "preferences": intent.get("preferences", []),
        "user_profile": intent.get("user_profile", ""),
    }

    full_prompt = f"""## System
你是淘天电商 AI 导购 Agent。基于检索到的商品和用户意图，输出可解释的 Top 3 推荐。
遵守 business_rules，按 output_format 返回 JSON。

## User Need
{user_need}

## Retrieved Products (RAG)
{chr(10).join(product_snippets)}

## Business Rules
{chr(10).join(f'- {r}' for r in business_rules)}

## Output Format
{output_format}
"""

    return {
        "user_need": user_need,
        "retrieved_products": product_snippets,
        "business_rules": business_rules,
        "output_format": output_format,
        "full_prompt_preview": full_prompt,
    }
