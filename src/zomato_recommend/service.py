"""Orchestrate query → Phase 4 context → Groq ranking."""

from __future__ import annotations

import os
import uuid
from typing import Any

from zomato_ingest.query import connect, filter_restaurants
from zomato_recommend.context import (
    additional_preferences_imply_family_friendly,
    build_llm_context,
)
from zomato_recommend.llm_rank import groq_rank_and_explain
from zomato_recommend.models import UserPreferences, budget_to_cost_bands


def run_recommendation(prefs: UserPreferences) -> dict[str, Any]:
    """
    Full path: SQLite filter → pre-sort → build_llm_context → Groq → merge rows for API response.
    """
    request_id = str(uuid.uuid4())
    max_llm = int(os.getenv("MAX_CANDIDATES_LLM", "25"))
    query_limit = int(os.getenv("QUERY_CANDIDATE_LIMIT", "200"))

    cost_bands = budget_to_cost_bands(prefs.budget)
    family = additional_preferences_imply_family_friendly(prefs.additional_preferences)

    conn = connect()
    try:
        rows = filter_restaurants(
            conn,
            city=prefs.location,
            cuisines=prefs.cuisines if prefs.cuisines else None,
            cuisine_mode="any",
            min_rating=prefs.min_rating,
            cost_bands=cost_bands,
            tag_family_friendly=family,
            limit=query_limit,
        )
    finally:
        conn.close()

    n_after_filter = len(rows)
    ctx = build_llm_context(prefs, rows, max_n=max_llm)
    n_to_llm = len(ctx["candidate_ids"])

    summary: str | None = None
    warnings: list[str] = []
    if n_after_filter == 0:
        warnings.append("No restaurants matched your filters. Try another city, budget, or cuisine.")
        return {
            "request_id": request_id,
            "summary": None,
            "results": [],
            "warnings": warnings,
            "debug": {
                "candidates_after_filter": 0,
                "n_sent_to_llm": 0,
            },
        }

    parsed, recs, w_extra = groq_rank_and_explain(ctx, top_k=prefs.desired_top_k)
    warnings.extend(w_extra)
    if isinstance(parsed, dict) and parsed.get("summary"):
        summary = str(parsed["summary"]).strip() or None

    by_id = ctx.get("candidates_by_id") or {}
    results: list[dict[str, Any]] = []
    for item in recs:
        rid = item["restaurant_id"]
        base = by_id.get(rid) or {}
        cuisines = base.get("cuisines") or []
        results.append(
            {
                "restaurant_id": rid,
                "name": base.get("name"),
                "cuisines": cuisines,
                "rating": base.get("rating"),
                "estimated_cost_label": base.get("cost_band"),
                "approx_cost_for_two": base.get("approx_cost_for_two"),
                "explanation": item.get("explanation"),
            }
        )

    return {
        "request_id": request_id,
        "summary": summary,
        "results": results,
        "warnings": warnings,
        "debug": {
            "candidates_after_filter": n_after_filter,
            "n_sent_to_llm": n_to_llm,
        },
    }
