"""
AI Shopping Guide Agent — Main Streamlit Application
淘天 AI 大模型产品经理 · 电商智能导购作品集 Demo
"""

import streamlit as st
import pandas as pd

from analytics import generate_mock_ab_test, get_tracking_events, format_ab_table
from llm_service import generate_follow_up_questions, LLM_API_KEY, LLM_PROVIDER
import re

from intent_parser import parse_natural_language_intent, CATEGORY_UI_REVERSE

try:
    from budget_parser import parse_budget_range
except ImportError:
    def parse_budget_range(query: str) -> dict | None:
        q = (
            query.replace("，", ",")
            .replace("－", "-")
            .replace("—", "-")
            .replace("～", "~")
        )
        sep = r"(?:到|至|-|~|－)"
        patterns: list[tuple[str, bool]] = [
            (rf"预算\s*(\d+(?:\.\d+)?\s*[kK])\s*{sep}\s*(\d+(?:\.\d+)?\s*[kK])", True),
            (rf"预算\s*(\d{{3,6}})\s*{sep}\s*(\d{{3,6}})", False),
            (rf"(\d+(?:\.\d+)?\s*[kK])\s*{sep}\s*(\d+(?:\.\d+)?\s*[kK])", True),
            (rf"(\d{{3,6}})\s*{sep}\s*(\d{{3,6}})", False),
        ]
        for pat, is_k in patterns:
            m = re.search(pat, q, re.I)
            if m:
                def _cn(tok: str) -> float:
                    s = tok.strip().lower().replace(" ", "")
                    if is_k or "k" in s:
                        return float(re.sub(r"[kK]", "", s)) * 1000
                    n = float(s)
                    return n * 1000 if n < 100 else n

                lo, hi = _cn(m.group(1)), _cn(m.group(2))
                lo, hi = min(lo, hi), max(lo, hi)
                return {"budget_min": lo, "budget_max": hi, "parsed_budget": hi}
        return None

from prompt_design import build_prompt_design
from recommender import (
    load_products,
    rank_products,
    generate_recommendation_explanation,
    build_comparison_table,
    get_score_breakdown_df,
    explain_non_recommendations,
)


def enrich_parsed_budget(query: str, parsed: dict) -> dict:
    """
    Always overlay budget range from budget_parser (fixes stale intent_parser).
    UI 展示与表单默认值都依赖此函数。
    """
    br = parse_budget_range(query.strip())
    if not br:
        return parsed
    out = dict(parsed)
    out["budget_min"] = br["budget_min"]
    out["budget_max"] = br["budget_max"]
    out["parsed_budget"] = br["parsed_budget"]
    range_hit = {
        "field": "budget_range",
        "value": f"{int(br['budget_min'])}-{int(br['budget_max'])}",
        "reason": f"预算范围：¥{int(br['budget_min']):,} - ¥{int(br['budget_max']):,}",
        "confidence": 0.96,
    }
    hits = [h for h in out.get("rule_hits", []) if h.get("field") not in ("budget", "budget_range")]
    out["rule_hits"] = [range_hit] + hits
    return out


def parse_nl_with_budget(query: str) -> dict:
    """NL intent parse + guaranteed budget_min / budget_max / parsed_budget."""
    return enrich_parsed_budget(query, parse_natural_language_intent(query))


def parse_user_intent(
    query: str,
    budget: float | None = None,
    category: str | None = None,
    preferences: list[str] | None = None,
    manual_override: bool = False,
    nl_parsed: dict | None = None,
) -> dict:
    """Merge NL parse with manual constraints (defined in app.py for stable imports)."""
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


st.set_page_config(
    page_title="AI Shopping Guide Agent",
    page_icon="🛒",
    layout="wide",
)

DEFAULT_QUERY = (
    "我想买一台适合留学生写代码和上课用的轻薄笔记本，"
    "预算 6000 左右，最好续航好一点，偶尔玩游戏。"
)

CATEGORY_OPTIONS = ["General", "Laptop", "Phone", "Headphone", "Skincare"]
PREFERENCE_OPTIONS = ["性价比", "性能", "轻便", "续航", "品牌", "评价", "低价"]


def _init_session_state() -> None:
    """Initialize session state for NL-first intent parsing flow."""
    if "initialized" not in st.session_state:
        parsed = parse_nl_with_budget(DEFAULT_QUERY)
        st.session_state.nl_parsed = parsed
        st.session_state.last_query = DEFAULT_QUERY
        st.session_state.form_budget = int(
            parsed.get("parsed_budget") or parsed.get("budget_max") or 6000
        )
        st.session_state.form_category = parsed.get("parsed_category_ui", "Laptop")
        st.session_state.form_preferences = list(parsed.get("parsed_preferences", ["轻便", "续航", "性能"]))
        st.session_state.manual_override = False
        st.session_state.show_results = False
        st.session_state.initialized = True
    elif "nl_parsed" not in st.session_state:
        st.session_state.nl_parsed = None
        st.session_state.last_query = ""
        st.session_state.form_budget = 6000
        st.session_state.form_category = "Laptop"
        st.session_state.form_preferences = ["轻便", "续航", "性能"]
        st.session_state.manual_override = False
        st.session_state.show_results = False


def _apply_parsed_to_form(parsed: dict) -> None:
    """Fill form defaults from NL parse result."""
    st.session_state.nl_parsed = parsed
    # 表单预算默认取 parsed_budget（= budget_max）
    st.session_state.form_budget = int(
        parsed.get("parsed_budget") or parsed.get("budget_max") or 6000
    )
    st.session_state.form_category = parsed.get("parsed_category_ui", "General")
    st.session_state.form_preferences = list(parsed.get("parsed_preferences", []))
    st.session_state.manual_override = False


def _detect_manual_override(parsed: dict, budget: float, category: str, preferences: list) -> bool:
    """Return True if user changed form fields away from last NL parse."""
    if not parsed:
        return False
    pb_max = parsed.get("budget_max") or parsed.get("parsed_budget")
    budget_diff = (budget != int(pb_max or 0)) if pb_max else (budget > 0)
    cat_diff = category != parsed.get("parsed_category_ui", "General")
    pref_diff = set(preferences) != set(parsed.get("parsed_preferences", []))
    return budget_diff or cat_diff or pref_diff


def _render_parse_result(parsed: dict) -> None:
    """Show NL parse preview after Parse Intent."""
    st.success("✅ Natural Language Intent Parsing · 自然语言需求解析完成")
    bmin, bmax = parsed.get("budget_min"), parsed.get("budget_max")
    if bmin and bmax:
        st.info(f"识别到预算范围：¥{int(bmin):,} - ¥{int(bmax):,}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("parsed_budget", f"¥{int(parsed['parsed_budget'])}" if parsed.get("parsed_budget") else "未识别")
    c2.metric("budget_min", f"¥{int(bmin)}" if bmin else "—")
    c3.metric("budget_max", f"¥{int(bmax)}" if bmax else "—")
    c4.metric("confidence", f"{parsed.get('confidence', 0):.0%}")

    st.write("**parsed_preferences**：", " · ".join(parsed.get("parsed_preferences", [])) or "—")
    st.write("**parsed_use_case**：", " · ".join(parsed.get("parsed_use_case", [])) or "—")

    with st.expander("rule_hit_reason · 规则命中详情"):
        for hit in parsed.get("rule_hits", []):
            st.markdown(
                f"- **{hit['field']}** = `{hit.get('value')}` · "
                f"confidence {hit.get('confidence', 0):.0%} · {hit.get('reason')}"
            )

PRODUCT_THINKING = {
    "pain_points": [
        "用户不会写精准搜索词，复合需求（编程+轻薄+续航）难以表达",
        "SKU 参数复杂，决策成本高，跳出率上升",
        "传统推荐是黑盒，用户不信任「为什么推这个」",
        "一次搜索不准，用户反复改写 Query，体验差",
    ],
    "business_goals": [
        "将 Search 升级为 Agent 导购，提升 **CTR → 加购率 → GMV**",
        "降低 Query 改写率，提高首次推荐命中率",
        "沉淀导购专属埋点数据，支撑排序模型迭代",
        "平衡用户体验与平台收益（profit_score 纳入排序）",
    ],
    "ai_solution": [
        "**NLU** 理解自然语言需求 → 结构化意图槽位",
        "**RAG** 从商品知识库召回候选 SKU",
        "**Multi-objective Ranking** 7 维打分 + 加权排序",
        "**Explainable Recommendation** 分数拆解 + 推荐理由 + 负向解释",
        "**Multi-turn** 追问澄清 → 下一轮精准推荐",
    ],
    "core_metrics": [
        "CTR（recommendation_click / exposure）",
        "Add-to-Cart Rate（加购率）",
        "Conversion Rate（转化率）",
        "Query Reformulation Rate（Query 改写率 ↓ 越好）",
        "User Satisfaction Score（推荐反馈）",
    ],
    "risks": [
        "LLM 幻觉 → RAG 约束，仅基于真实 SKU 字段生成",
        "推荐偏差（只推高价）→ 多目标排序 + AB 监控",
        "延迟 → Mock < 1s；真实 LLM 可异步生成理由",
        "合规 → 标注「可能风险」，不做绝对化承诺",
    ],
}


def render_product_thinking() -> None:
    """Product Thinking — PM 视角的产品逻辑展示。"""
    st.subheader("💡 Product Thinking · 产品思考")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**用户痛点 User Pain Points**")
        for p in PRODUCT_THINKING["pain_points"]:
            st.markdown(f"- {p}")
        st.markdown("**业务目标 Business Goals**")
        for g in PRODUCT_THINKING["business_goals"]:
            st.markdown(f"- {g}")
    with c2:
        st.markdown("**AI 解决方案 AI Solution**")
        for s in PRODUCT_THINKING["ai_solution"]:
            st.markdown(f"- {s}")
        st.markdown("**核心指标 Core Metrics**")
        for m in PRODUCT_THINKING["core_metrics"]:
            st.markdown(f"- `{m}`")
        st.markdown("**潜在风险 Risks & Guardrails**")
        for r in PRODUCT_THINKING["risks"]:
            st.markdown(f"- ⚠️ {r}")


def main() -> None:
    _init_session_state()

    st.title("🛒 AI Shopping Guide Agent")
    st.markdown(
        "**基于大模型的电商智能导购 Agent** · 淘天 AI 大模型产品经理作品集 · "
        f"LLM Mode: `{LLM_PROVIDER}`"
        + (" ✅" if LLM_API_KEY else " · Mock（无需 API Key）")
    )
    st.caption(
        "Search → Agent · RAG Recall · Multi-objective Ranking · "
        "Explainable Recommendation · Conversion-oriented Metrics"
    )

    with st.sidebar:
        st.header("📖 About This Demo")
        st.markdown(
            """
            **定位**：不是 Chatbot，而是有召回、排序、度量、AB 实验的 **导购 Agent**。

            **Agent 链路**  
            Query → Intent → RAG → Rank → Explain → Follow-up → AB

            **淘天场景**  
            搜索升级 · 智能导购 · GMV · 用户体验
            """
        )
        st.metric("商品库 SKU", len(load_products()))
        st.divider()
        st.subheader("Tracking Events · 埋点")
        for ev in get_tracking_events():
            with st.expander(ev["event"]):
                st.caption(ev["meaning"])

    render_product_thinking()
    st.divider()

    st.subheader("💬 输入购物需求 · Shopping Query")
    st.info(
        "自然语言输入是主入口，预算/品类/偏好是可编辑的辅助约束。"
        "这样模拟真实电商 AI 导购中，从用户模糊需求到结构化推荐条件的过程。"
    )

    query = st.text_area(
        "自然语言需求 Natural Language Query（主入口）",
        value=DEFAULT_QUERY,
        height=100,
        key="user_query",
    )

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        parse_clicked = st.button("🔍 解析需求 / Parse Intent", use_container_width=True)
    with btn_col2:
        generate_clicked = st.button(
            "🚀 Generate Recommendation · 生成推荐", type="primary", use_container_width=True
        )

    if parse_clicked and query.strip():
        parsed = parse_nl_with_budget(query)
        _apply_parsed_to_form(parsed)
        st.session_state.last_query = query.strip()
        st.rerun()

    st.markdown("**辅助约束 · 可手动微调 Manual Constraints**")
    col1, col2, col3 = st.columns(3)
    with col1:
        budget = st.number_input(
            "预算 Budget (¥)",
            min_value=0,
            max_value=50000,
            step=500,
            key="form_budget",
        )
    with col2:
        category = st.selectbox(
            "品类 Category",
            CATEGORY_OPTIONS,
            key="form_category",
        )
    with col3:
        preferences = st.multiselect(
            "偏好 Preferences",
            PREFERENCE_OPTIONS,
            key="form_preferences",
        )

    if st.session_state.nl_parsed and st.session_state.last_query == query.strip():
        _render_parse_result(st.session_state.nl_parsed)
        if _detect_manual_override(st.session_state.nl_parsed, budget, category, preferences):
            st.warning("⚠️ Manual override detected · 用户已手动调整约束（以当前控件值为准）")
            st.session_state.manual_override = True
        else:
            st.session_state.manual_override = False

    if generate_clicked:
        if not query.strip():
            st.warning("请输入购物需求。")
        else:
            need_fresh_parse = (
                st.session_state.nl_parsed is None
                or st.session_state.last_query != query.strip()
            )
            if need_fresh_parse:
                parsed = parse_nl_with_budget(query)
                _apply_parsed_to_form(parsed)
                st.session_state.last_query = query.strip()
                use_budget = float(
                    parsed.get("budget_max") or parsed.get("parsed_budget") or 0
                )
                use_category = parsed.get("parsed_category_ui", "General")
                use_preferences = list(parsed.get("parsed_preferences", []))
                manual_override = False
            else:
                use_budget = float(budget)
                use_category = category
                use_preferences = preferences
                manual_override = _detect_manual_override(
                    st.session_state.nl_parsed, budget, category, preferences
                )

            run_agent(
                query=query.strip(),
                budget=use_budget if use_budget > 0 else None,
                category=use_category,
                preferences=use_preferences,
                manual_override=manual_override,
                nl_parsed=st.session_state.nl_parsed,
            )


def run_agent(
    query: str,
    budget: float | None,
    category: str,
    preferences: list[str],
    manual_override: bool = False,
    nl_parsed: dict | None = None,
) -> None:
    if not query.strip():
        st.warning("请输入购物需求。")
        return

    with st.spinner("Agent Pipeline: Intent Parsing → RAG Recall → Multi-objective Ranking…"):
        intent = parse_user_intent(
            query,
            budget=budget,
            category=category,
            preferences=preferences,
            manual_override=manual_override,
            nl_parsed=nl_parsed,
        )
        ranked = rank_products(intent)
        top3 = ranked.head(3)
        top_dicts = top3.to_dict(orient="records")
        explanations = generate_recommendation_explanation(intent, top_dicts)
        follow_ups = generate_follow_up_questions(intent)
        non_recs = explain_non_recommendations(ranked, intent)
        prompt_design = build_prompt_design(intent, top_dicts)
        ab = generate_mock_ab_test(query)

    # ── 1. User Intent Understanding ─────────────────────────────────────
    st.divider()
    st.subheader("1 · User Intent Understanding · 用户需求理解")

    if intent.get("manual_override"):
        st.warning("⚠️ Manual override detected · 用户已手动调整约束，推荐以当前控件值为准")

    st.markdown("**Natural Language Intent Parsing · 自然语言需求解析**")
    bmin, bmax = intent.get("budget_min"), intent.get("budget_max")
    if bmin and bmax:
        st.info(f"识别到预算范围：¥{int(bmin):,} - ¥{int(bmax):,}")

    ic1, ic2, ic3, ic4, ic5 = st.columns(5)
    ic1.metric("parsed_category", intent.get("parsed_category_ui", intent["category"]))
    ic2.metric("parsed_budget", f"¥{int(intent['parsed_budget'])}" if intent.get("parsed_budget") else "未识别")
    ic3.metric("budget_min", f"¥{int(bmin)}" if bmin else "—")
    ic4.metric("budget_max", f"¥{int(bmax)}" if bmax else "—")
    ic5.metric("confidence", f"{intent.get('confidence', 0):.0%}")

    st.write("**raw_query · 原始输入**：", intent["raw_query"])
    st.write("**parsed_preferences · 解析偏好**：", " · ".join(intent.get("parsed_preferences", [])))
    st.write("**parsed_use_case · 使用场景**：", " · ".join(intent.get("parsed_use_case", [])))
    st.write("**最终生效 · Active Constraints**：")
    if bmin and bmax:
        st.write(f"- 预算范围 `¥{int(bmin):,} - ¥{int(bmax):,}`（候选价格 ≤ ¥{int(bmax):,}）")
    else:
        st.write(f"- 预算上限 `¥{int(bmax):,}`" if bmax else "- 预算上限 `未明确`")
    st.write(f"- 品类 `{intent['category']}`")
    st.write(f"- 偏好 {' · '.join(intent['preferences'])}")
    st.metric("RAG 召回 Recall", f"{len(ranked)} SKU")

    with st.expander("rule_hit_reason · 规则命中详情"):
        for hit in intent.get("rule_hits", []):
            st.markdown(
                f"- **{hit['field']}** = `{hit.get('value')}` · "
                f"confidence {hit.get('confidence', 0):.0%} · {hit.get('reason')}"
            )

    st.info(intent["summary"])
    ic5, ic6 = st.columns(2)
    ic5.metric("用户画像 Profile", intent["user_profile"])
    ic6.metric("use_case_keys", " · ".join(intent.get("use_cases", [])))

    # ── 2. RAG Recall ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("2 · RAG Recall · 商品候选召回")
    show_cols = ["product_id", "product_name", "brand", "price", "rating", "sales", "final_score"]
    st.dataframe(
        ranked[show_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "final_score": st.column_config.ProgressColumn("final_score", min_value=0, max_value=100),
            "price": st.column_config.NumberColumn("价格(¥)", format="¥%d"),
        },
    )

    # ── 3. Multi-objective Ranking · Top 3 ─────────────────────────────────
    st.divider()
    st.subheader("3 · Multi-objective Ranking · 多目标排序 Top 3")
    for exp in explanations:
        with st.container(border=True):
            st.markdown(f"### 🏅 {exp['rank']} · {exp['product_name']}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**✅ Explainable Recommendation · 为什么推荐**  \n{exp['why']}")
                st.markdown(f"**👥 Target User · 适合人群**  \n{exp['audience']}")
            with c2:
                st.markdown(f"**⚠️ Risk · 潜在风险**  \n{exp['risks']}")
                st.caption(exp["llm_summary"])

    # ── 4. Product Comparison ──────────────────────────────────────────────
    st.divider()
    st.subheader("4 · Product Comparison · 商品对比表")
    st.dataframe(build_comparison_table(top3), use_container_width=True, hide_index=True)

    # ── 5. Recommendation Score Breakdown ──────────────────────────────────
    st.divider()
    st.subheader("5 · Recommendation Score Breakdown · 推荐分数拆解")
    st.caption(
        "7 维打分 + final_score · 体现 Multi-objective Optimization，权重可在 AB 实验中动态调整"
    )
    score_cols = [
        "category_score", "budget_score", "rating_score", "sales_score",
        "preference_score", "stock_score", "profit_score", "final_score",
    ]
    st.dataframe(
        top3[["product_name"] + score_cols],
        use_container_width=True,
        hide_index=True,
    )
    tabs = st.tabs([f"Top {i+1} Breakdown" for i in range(len(top_dicts))])
    for tab, prod in zip(tabs, top_dicts):
        with tab:
            st.markdown(f"**{prod['product_name']}** · final_score = **{prod['final_score']:.1f}**")
            breakdown_df = get_score_breakdown_df(prod)
            st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
            chart_df = breakdown_df[breakdown_df["Score Dimension"] != "final_score · 综合得分"]
            st.bar_chart(chart_df.set_index("Score Dimension")["Score"])

    # ── 6. Why not recommend others? ───────────────────────────────────────
    st.divider()
    st.subheader("6 · Why Not Recommend Others? · 为什么没有推荐其他商品")
    st.caption("负向可解释性 · 帮助用户理解排序逻辑，降低「黑盒推荐」不信任感")
    if non_recs:
        for item in non_recs:
            with st.expander(
                f"❌ {item['product_name']} · final_score {item['final_score']} "
                f"(gap vs Top1: -{item['score_gap_vs_top1']})"
            ):
                for r in item["reasons"]:
                    st.markdown(f"- {r}")
    else:
        st.write("候选集较小，所有商品均已进入 Top 推荐。")

    # ── 7. Prompt Design ───────────────────────────────────────────────────
    st.divider()
    st.subheader("7 · Prompt Design · Prompt 工程设计")
    st.caption("展示 Agent 如何将 User Need + RAG Context + Business Rules 组装为 LLM Prompt")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**User Need · 用户需求**")
        st.json(prompt_design["user_need"])
        st.markdown("**Business Rules · 业务规则**")
        for rule in prompt_design["business_rules"]:
            st.markdown(f"- {rule}")
    with pc2:
        st.markdown("**Retrieved Products · RAG 检索结果**")
        for p in prompt_design["retrieved_products"]:
            st.markdown(f"- {p}")
        st.markdown("**Output Format · 输出格式**")
        st.json(prompt_design["output_format"])
    with st.expander("📄 Full Prompt Preview · 完整 Prompt 预览"):
        st.code(prompt_design["full_prompt_preview"], language="markdown")

    # ── 8. Follow-up Questions ─────────────────────────────────────────────
    st.divider()
    st.subheader("8 · Follow-up Questions · 多轮追问澄清")
    for q in follow_ups:
        st.markdown(f"- ❓ {q}")

    # ── 9. Mock AB Experiment ──────────────────────────────────────────────
    st.divider()
    st.subheader("9 · Mock AB Experiment · 模拟 AB 实验 · Conversion-oriented Metrics")
    st.markdown(f"**Hypothesis · 实验假设**：{ab['hypothesis']}")
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Duration · 实验天数", f"{ab['duration_days']} 天")
    mc2.metric("Sample Size · 样本量", f"{ab['sample_size']:,}")
    mc3.metric("GMV Impact · GMV 预估", ab["gmv_impact_estimate"])
    st.dataframe(format_ab_table(ab), use_container_width=True, hide_index=True)
    ab_col1, ab_col2 = st.columns(2)
    with ab_col1:
        st.markdown("**A · Control · 传统关键词搜索**")
        st.json(ab["control"])
    with ab_col2:
        st.markdown("**B · Treatment · AI 导购 Agent**")
        st.json(ab["treatment"])


if __name__ == "__main__":
    main()
