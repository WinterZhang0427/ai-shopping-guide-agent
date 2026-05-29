"""
Natural Language Intent Parsing / 自然语言需求解析
Standalone module — avoids import conflicts with llm_service.
"""

from __future__ import annotations

import re
from typing import Any

from budget_parser import convert_num, parse_budget_range

CATEGORY_UI_MAP: dict[str, str] = {
    "laptop": "Laptop",
    "phone": "Phone",
    "headphone": "Headphone",
    "skincare": "Skincare",
    "general": "General",
}
CATEGORY_UI_REVERSE = {v: k for k, v in CATEGORY_UI_MAP.items()}

CATEGORY_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("laptop", "品类规则：笔记本/电脑/轻薄本/游戏本/写代码", (
        "笔记本", "电脑", "轻薄本", "游戏本", "laptop", "macbook", "写代码",
    )),
    ("phone", "品类规则：手机/拍照/续航手机", (
        "手机", "phone", "iphone", "拍照", "续航手机", "华为", "小米",
    )),
    ("headphone", "品类规则：耳机/降噪/通勤/蓝牙", (
        "耳机", "headphone", "airpods", "降噪", "蓝牙耳机", "蓝牙",
    )),
    ("skincare", "品类规则：护肤/面霜/精华/防晒", (
        "护肤", "面霜", "精华", "防晒", "skincare", "抗老", "保湿",
    )),
]

PREFERENCE_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("轻便", "偏好规则：轻薄/便携/通勤", ("轻薄", "便携", "通勤", "轻便", "轻")),
    ("续航", "偏好规则：续航/电池/待机", ("续航", "电池", "待机")),
    ("性能", "偏好规则：性能/游戏/编程/跑模型", (
        "性能", "游戏", "写代码", "编程", "开发", "跑模型",
    )),
    ("评价", "偏好规则：评价/口碑/评分", ("评价", "口碑", "评分", "评价高", "好评")),
    ("性价比", "偏好规则：便宜/性价比/划算", ("便宜", "性价比", "划算")),
    ("品牌", "偏好规则：品牌/大牌/售后", ("品牌", "大牌", "售后", "apple", "索尼")),
    ("低价", "偏好规则：低价/千元", ("低价", "千元")),
]

USE_CASE_RULES: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("学习场景", "study", "场景规则：留学生/上课/写作业", (
        "留学生", "上课", "写作业", "学习", "学生", "网课",
    )),
    ("编程场景", "coding", "场景规则：写代码/编程/开发", (
        "写代码", "编程", "开发", "code", "ide", "跑模型",
    )),
    ("游戏场景", "gaming", "场景规则：游戏/原神/崩铁等", (
        "游戏", "原神", "崩铁", "三角洲", "明日方舟", "gaming", "玩",
    )),
    ("通勤场景", "commute", "场景规则：通勤/地铁/出差", (
        "通勤", "地铁", "出差",
    )),
]


def parse_natural_language_intent(query: str) -> dict[str, Any]:
    """Parse budget / category / preferences / use_case from Chinese NL query."""
    q = query.strip()
    q_lower = q.lower()
    rule_hits: list[dict[str, Any]] = []

    budget_info, budget_hits = _extract_budget_with_rules(q)
    rule_hits.extend(budget_hits)

    category_key, cat_hit = _detect_category_with_rule(q_lower)
    if cat_hit:
        rule_hits.append(cat_hit)

    preferences, pref_hits = _detect_preferences_with_rules(q_lower)
    rule_hits.extend(pref_hits)

    use_case_labels, use_case_keys, uc_hits = _detect_use_cases_with_rules(q_lower)
    rule_hits.extend(uc_hits)

    confidences = [h["confidence"] for h in rule_hits if "confidence" in h]
    overall_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "raw_query": query,
        "parsed_budget": budget_info.get("parsed_budget"),
        "budget_min": budget_info.get("budget_min"),
        "budget_max": budget_info.get("budget_max"),
        "parsed_category": category_key,
        "parsed_category_ui": CATEGORY_UI_MAP.get(category_key, "General"),
        "parsed_preferences": preferences,
        "parsed_use_case": use_case_labels,
        "use_case_keys": use_case_keys,
        "rule_hits": rule_hits,
        "confidence": overall_confidence,
    }


def _normalize_amount(val: str) -> float:
    """Parse numeric string; supports k/K suffix."""
    return convert_num(val)


def _parse_amount_token(token: str) -> float:
    """Parse 5000 / 5k / 5K into yuan amount."""
    return convert_num(token.strip(), force_k="k" in token.lower())


def _chinese_token_to_number(token: str) -> float | None:
    """Parse 五千 / 一万 / 七千 等。"""
    token = token.strip()
    mapping = {
        "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
    }
    if "万" in token:
        for ch, num in mapping.items():
            if token.startswith(ch):
                return num * 10000
        return 10000
    if "千" in token:
        for ch, num in mapping.items():
            if token.startswith(ch):
                return num * 1000
        return 1000
    return None


def _extract_budget_with_rules(text: str) -> tuple[dict[str, float | None], list[dict]]:
    """
    Extract budget_min, budget_max, parsed_budget from Chinese text.
    Range first (parse_budget_range); then single cap (budget_min=None).
    """
    hits: list[dict] = []

    budget_range = parse_budget_range(text)
    if budget_range:
        lo = float(budget_range["budget_min"])
        hi = float(budget_range["budget_max"])
        hits.append({
            "field": "budget_range",
            "value": f"{int(lo)}-{int(hi)}",
            "reason": f"预算范围：¥{int(lo):,} - ¥{int(hi):,}",
            "confidence": 0.96,
        })
        return {
            "budget_min": lo,
            "budget_max": hi,
            "parsed_budget": float(budget_range["parsed_budget"]),
        }, hits

    # Chinese range: 五千到七千
    cn_range = re.search(
        r"([一二两三四五六七八九十]+千|[一二两三四五六七八九十]+万)\s*(?:到|至)\s*"
        r"([一二两三四五六七八九十]+千|[一二两三四五六七八九十]+万)",
        text,
    )
    if cn_range:
        lo = _chinese_token_to_number(cn_range.group(1))
        hi = _chinese_token_to_number(cn_range.group(2))
        if lo and hi:
            if lo > hi:
                lo, hi = hi, lo
            hits.append({
                "field": "budget_range",
                "value": f"{int(lo)}-{int(hi)}",
                "reason": f"预算范围：{cn_range.group(0)}",
                "confidence": 0.92,
            })
            return {
                "budget_min": lo, "budget_max": hi, "parsed_budget": hi,
            }, hits

    # --- Single budget cap (never bare 预算\\d+ — avoids stealing range prefix) ---
    single_patterns: list[tuple[str, str, float, str]] = [
        (r"预算\s*(\d{3,6})\s*左右", "预算规则：预算{N}左右", 0.95, "around"),
        (r"预算\s*(\d+(?:\.\d+)?)\s*[kK]\s*左右", "预算规则：预算{N}k左右", 0.95, "around"),
        (r"预算\s*(\d+(?:\.\d+)?)\s*[kK]", "预算规则：预算{N}k", 0.93, "cap"),
        (r"不超过\s*(\d{3,6})", "预算规则：不超过{N}", 0.92, "cap"),
        (r"不超过\s*(\d+(?:\.\d+)?)\s*[kK]", "预算规则：不超过{N}k", 0.92, "cap"),
        (r"(\d{3,6})\s*以内", "预算规则：{N}以内", 0.90, "cap"),
        (r"(\d+(?:\.\d+)?)\s*[kK]\s*以内", "预算规则：{N}k以内", 0.90, "cap"),
        (r"(\d{3,6})\s*左右", "预算规则：{N}左右", 0.85, "around"),
        (r"(\d{3,6})\s*元", "预算规则：{N}元", 0.80, "cap"),
        (r"(?<![到至\-~－\d])(\d+(?:\.\d+)?)\s*[kK](?!\s*(?:到|至|-|~|－))", "预算规则：{N}k", 0.85, "cap"),
    ]
    for pat, reason_tpl, conf, _kind in single_patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = _parse_amount_token(m.group(1))
            hits.append({
                "field": "budget", "value": val,
                "reason": reason_tpl.replace("{N}", str(int(val))), "confidence": conf,
            })
            return {
                "budget_min": None, "budget_max": val, "parsed_budget": val,
            }, hits

    cn_single = [
        (r"([一二两三四五六七八九十]+)\s*万\s*以内", "预算规则：{M}以内", 0.88),
        (r"([一二两三四五六七八九十]+)\s*万\s*左右", "预算规则：{M}左右", 0.88),
        (r"([一二两三四五六七八九十]+)\s*万", "预算规则：{M}", 0.85),
    ]
    for pat, reason_tpl, conf in cn_single:
        m = re.search(pat, text)
        if m:
            val = _chinese_token_to_number(m.group(1) + "万")
            if val:
                hits.append({
                    "field": "budget", "value": val,
                    "reason": reason_tpl.replace("{M}", m.group(0)), "confidence": conf,
                })
                return {
                    "budget_min": None, "budget_max": val, "parsed_budget": val,
                }, hits

    return {"budget_min": None, "budget_max": None, "parsed_budget": None}, hits


def _detect_category_with_rule(q: str) -> tuple[str, dict | None]:
    for cat_key, reason, kws in CATEGORY_RULES:
        matched = [k for k in kws if k in q]
        if matched:
            return cat_key, {
                "field": "category", "value": CATEGORY_UI_MAP[cat_key],
                "reason": f"{reason}（命中：{matched[0]}）", "confidence": 0.90,
            }
    return "general", None


def _detect_preferences_with_rules(q: str) -> tuple[list[str], list[dict]]:
    prefs: list[str] = []
    hits: list[dict] = []
    for label, reason, kws in PREFERENCE_RULES:
        matched = [k for k in kws if k in q]
        if matched:
            prefs.append(label)
            hits.append({
                "field": "preference", "value": label,
                "reason": f"{reason}（命中：{matched[0]}）", "confidence": 0.85,
            })
    if not prefs:
        prefs = ["性价比"]
        hits.append({
            "field": "preference", "value": "性价比",
            "reason": "默认偏好：未识别到显式偏好，使用性价比", "confidence": 0.50,
        })
    return prefs, hits


def _detect_use_cases_with_rules(q: str) -> tuple[list[str], list[str], list[dict]]:
    labels: list[str] = []
    keys: list[str] = []
    hits: list[dict] = []
    for label, key, reason, kws in USE_CASE_RULES:
        matched = [k for k in kws if k in q]
        if matched:
            labels.append(label)
            keys.append(key)
            hits.append({
                "field": "use_case", "value": label,
                "reason": f"{reason}（命中：{matched[0]}）", "confidence": 0.88,
            })
    if "轻薄" in q or "便携" in q:
        if "portability" not in keys:
            keys.append("portability")
    if "续航" in q and "battery life" not in keys:
        keys.append("battery life")
    return labels, keys, hits


def parse_user_intent(
    query: str,
    budget: float | None = None,
    category: str | None = None,
    preferences: list[str] | None = None,
    manual_override: bool = False,
    nl_parsed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Merge NL parse with manual widget values.
    manual_override=True → 手动 budget 作为 budget_max，保留 NL 解析的 budget_min。
    """
    nl = nl_parsed if nl_parsed else parse_natural_language_intent(query)

    # Always re-parse budget from raw query (range before single; avoids stale nl_parsed)
    budget_range = parse_budget_range(query)
    if budget_range:
        nl_bmin = budget_range["budget_min"]
        nl_bmax = budget_range["budget_max"]
        nl_parsed_budget = budget_range["parsed_budget"]
    else:
        single_info, _ = _extract_budget_with_rules(query)
        if single_info.get("budget_max") is not None or single_info.get("parsed_budget") is not None:
            nl_bmin = single_info.get("budget_min")
            nl_bmax = single_info.get("budget_max")
            nl_parsed_budget = single_info.get("parsed_budget")
        else:
            nl_bmin = nl.get("budget_min")
            nl_bmax = nl.get("budget_max")
            nl_parsed_budget = nl.get("parsed_budget")
    parsed_category = nl.get("parsed_category", "general")
    parsed_category_ui = nl.get("parsed_category_ui", "General")
    parsed_preferences = nl.get("parsed_preferences", [])
    parsed_use_case = nl.get("parsed_use_case", [])
    use_case_keys = nl.get("use_case_keys", []) or ["general shopping"]

    if category and category != "General":
        final_category = CATEGORY_UI_REVERSE.get(category, category.lower())
    else:
        final_category = parsed_category

    final_preferences = preferences if preferences is not None else parsed_preferences

    # NL range/cap wins unless user manually overrode the form
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

    final_budget = final_bmax  # compat: budget = upper cap

    if final_bmin and final_bmax:
        b_str = f"¥{int(final_bmin)} - ¥{int(final_bmax)}"
    elif final_bmax:
        b_str = f"约 ¥{int(final_bmax)}"
    else:
        b_str = "未明确"

    override_note = "（含手动调整）" if manual_override else ""

    return {
        "raw_query": query,
        "category": final_category,
        "parsed_category": parsed_category,
        "parsed_category_ui": parsed_category_ui,
        "budget": final_budget,
        "parsed_budget": final_parsed,
        "budget_min": final_bmin,
        "budget_max": final_bmax,
        "use_cases": use_case_keys,
        "parsed_use_case": parsed_use_case,
        "preferences": final_preferences,
        "parsed_preferences": parsed_preferences,
        "rule_hits": nl.get("rule_hits", []),
        "confidence": nl.get("confidence", 0.0),
        "manual_override": manual_override,
        "user_profile": _infer_user_profile(query),
        "summary": (
            f"识别品类：**{final_category}** · 预算 **{b_str}**{override_note} · "
            f"已从自然语言解析结构化推荐条件。"
        ),
    }


def _infer_user_profile(q: str) -> str:
    if "留学生" in q:
        return "Overseas student · coding + study"
    if "学生" in q:
        return "Student · budget-sensitive"
    if "商务" in q:
        return "Business user · brand & reliability"
    return "General online shopper"


__all__ = [
    "CATEGORY_UI_MAP",
    "CATEGORY_UI_REVERSE",
    "parse_natural_language_intent",
    "parse_budget_range",
    "parse_user_intent",
    "convert_num",
]
