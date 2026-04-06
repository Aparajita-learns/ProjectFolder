"""Groq chat completion: rank + explain with JSON output (Phase 5 hook for Phase 4 context)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

_GROQ_BASE = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


def _client() -> OpenAI:
    key = (os.getenv("GROQ_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    return OpenAI(api_key=key, base_url=_GROQ_BASE)


def _parse_json_object(text: str) -> dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.lstrip().startswith("json"):
                inner = inner.lstrip()[4:].lstrip()
            t = inner.strip()
    return json.loads(t)


def _fallback_results(
    ctx: dict[str, Any],
    top_k: int,
    reason: str,
) -> tuple[list[dict[str, Any]], str | None]:
    slim = ctx.get("candidates_slim") or []
    out: list[dict[str, Any]] = []
    for i, row in enumerate(slim[:top_k]):
        rid = row.get("restaurant_id")
        if not rid:
            continue
        out.append(
            {
                "restaurant_id": rid,
                "rank": i + 1,
                "explanation": f"Selected by rating and cost fit ({reason}).",
            }
        )
    return out, f"LLM fallback: {reason}" if out else None


def groq_rank_and_explain(
    ctx: dict[str, Any],
    *,
    top_k: int,
    temperature: float = 0.25,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """
    Call Groq; return (raw_parsed_or_empty, recommendations, warnings).

    Each recommendation: restaurant_id, rank, explanation.
    """
    warnings: list[str] = []
    allowed = set(ctx.get("candidate_ids") or [])
    if not allowed:
        return {}, [], ["No candidates matched filters; try relaxing location, budget, or cuisine."]

    schema_hint = json.dumps(
        {
            "summary": "One short paragraph.",
            "recommendations": [
                {
                    "restaurant_id": "<id from list>",
                    "rank": 1,
                    "explanation": "Why this matches the user (2-4 sentences).",
                }
            ],
        },
        indent=2,
    )

    user_msg = (
        ctx["user_content"]
        + f"\n\nReturn JSON with at most {top_k} recommendations, ordered best-first. Schema:\n{schema_hint}\n"
        "Include only restaurant_id values from the candidate list. No markdown, JSON only."
    )

    client = _client()
    resp = client.chat.completions.create(
        model=_DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": ctx["system_hints"]},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature,
        max_tokens=1200,
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        recs, w = _fallback_results(ctx, top_k, "empty model response")
        if w:
            warnings.append(w)
        return {}, recs, warnings

    try:
        data = _parse_json_object(text)
    except (json.JSONDecodeError, ValueError) as e:
        recs, w = _fallback_results(ctx, top_k, f"JSON parse error: {e}")
        if w:
            warnings.append(w)
        return {}, recs, warnings

    raw_recs = data.get("recommendations") if isinstance(data, dict) else None
    if not isinstance(raw_recs, list):
        recs, w = _fallback_results(ctx, top_k, "missing recommendations array")
        if w:
            warnings.append(w)
        return data if isinstance(data, dict) else {}, recs, warnings

    cleaned: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_recs:
        if not isinstance(item, dict):
            continue
        rid = item.get("restaurant_id")
        if not rid or rid not in allowed or rid in seen:
            continue
        seen.add(rid)
        cleaned.append(
            {
                "restaurant_id": rid,
                "rank": int(item.get("rank", len(cleaned) + 1)),
                "explanation": str(item.get("explanation", "")).strip() or "Matches your filters.",
            }
        )
        if len(cleaned) >= top_k:
            break

    if not cleaned:
        recs, w = _fallback_results(ctx, top_k, "no valid IDs from model")
        if w:
            warnings.append(w)
        return data if isinstance(data, dict) else {}, recs, warnings

    cleaned.sort(key=lambda x: x["rank"])
    return data if isinstance(data, dict) else {}, cleaned, warnings
