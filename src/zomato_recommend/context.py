"""
Phase 4: pre-LLM ranking, Top-N selection, and prompt context serialization.
"""

from __future__ import annotations

import json
import re
from typing import Any

from zomato_recommend.models import BudgetBand, UserPreferences

_BAND_ORDER = {"low": 0, "medium": 1, "high": 2}


def _band_distance(cost_band: str | None, budget: BudgetBand) -> int:
    if not cost_band or cost_band not in _BAND_ORDER:
        return 99
    return abs(_BAND_ORDER[cost_band] - _BAND_ORDER[budget])


def sort_candidates_pre_llm(candidates: list[dict[str, Any]], budget: BudgetBand) -> list[dict[str, Any]]:
    """
    Sort: higher rating first (nulls last), then closer cost_band to budget, then name.
    """
    def key(row: dict[str, Any]) -> tuple:
        r = row.get("rating")
        has_r = r is not None
        rv = -float(r) if has_r else 0.0
        bd = _band_distance(row.get("cost_band"), budget)
        name = (row.get("name") or "").lower()
        return (not has_r, rv, bd, name)

    return sorted(candidates, key=key)


def build_llm_context(
    prefs: UserPreferences,
    candidates: list[dict[str, Any]],
    *,
    max_n: int,
) -> dict[str, Any]:
    """
    Build bounded, auditable context for the LLM.

    Returns:
        system_hints: short instruction block
        user_content: preferences restatement + JSON candidate list
        candidate_ids: ordered ids sent to the model
        candidates_slim: list of dicts actually included
    """
    if max_n < 1:
        max_n = 1
    ordered = sort_candidates_pre_llm(candidates, prefs.budget)
    slim_raw = ordered[:max_n]
    slim: list[dict[str, Any]] = []
    for c in slim_raw:
        slim.append(
            {
                "restaurant_id": c.get("restaurant_id"),
                "name": c.get("name"),
                "cuisines": c.get("cuisines") or [],
                "rating": c.get("rating"),
                "cost_band": c.get("cost_band"),
                "city": c.get("city"),
                "area": c.get("area"),
                "approx_cost_for_two": c.get("approx_cost_for_two"),
            }
        )
    ids = [s["restaurant_id"] for s in slim if s.get("restaurant_id")]

    prefs_lines = [
        f"Location (city): {prefs.location}",
        f"Budget band: {prefs.budget}",
        f"Cuisines of interest: {', '.join(prefs.cuisines) if prefs.cuisines else 'any'}",
        f"Minimum rating: {prefs.min_rating}" if prefs.min_rating is not None else "Minimum rating: none",
        f"Additional notes: {prefs.additional_preferences[:500]}" if prefs.additional_preferences else "",
    ]
    user_block = "\n".join(line for line in prefs_lines if line)

    user_content = (
        "## User preferences\n"
        f"{user_block}\n\n"
        "## Candidate restaurants (use only these IDs; do not invent venues)\n"
        f"```json\n{json.dumps(slim, indent=2)}\n```\n"
    )

    system_hints = (
        "You are a dining recommendation assistant. "
        "You may ONLY recommend restaurants whose restaurant_id appears in the candidate JSON. "
        "Respond with valid JSON only, no markdown fences, matching the schema in the user message."
    )

    return {
        "system_hints": system_hints,
        "user_content": user_content,
        "candidate_ids": ids,
        "candidates_slim": slim,
        "candidates_by_id": {
            s["restaurant_id"]: c
            for s, c in zip(slim, slim_raw, strict=True)
            if s.get("restaurant_id")
        },
    }


def additional_preferences_imply_family_friendly(text: str) -> bool | None:
    if not text or not text.strip():
        return None
    t = text.lower()
    if re.search(r"\bfamily|kid|kids|child|children\b", t):
        return True
    return None
