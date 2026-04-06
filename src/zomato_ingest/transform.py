"""
Normalize raw Hugging Face Zomato rows to the Phase 1 target schema.

Cost bands (INR, approx cost for two — explicit thresholds, not percentiles):
  - low:    cost <= 400
  - medium: 401 <= cost <= 1000
  - high:   cost > 1000

Missing numeric cost → cost_band is None (stored as empty string in Parquet row if needed).
Ratings: parse values like "4.1/5"; Zomato "NEW" or unparsable → rating is None (no imputation).
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

# --- Cost band rules (INR, approximate cost for two people) ---
LOW_BAND_MAX_INR = 400
HIGH_BAND_MIN_INR = 1001

# Light cuisine normalization (extend in one place for query layer later)
CUISINE_SYNONYMS: dict[str, str] = {
    "fastfood": "fast food",
    "northindian": "north indian",
    "southindian": "south indian",
}

_FAMILY_KEYWORDS = ("family", "kid", "kids", "child", "children")


def _clean_str(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in ("nan", "none", ""):
        return ""
    return " ".join(s.split())


def _normalize_cuisine_token(token: str) -> str:
    t = token.strip().lower()
    t = CUISINE_SYNONYMS.get(t.replace(" ", ""), t)
    return t


def normalize_cuisine_query(token: str) -> str:
    """Normalize a single user/query cuisine token (same rules as ingest)."""
    return _normalize_cuisine_token(token)


def normalize_city_query(city: str) -> str:
    """Normalize city for strict equality match (SQLite ``lower()``-compatible, collapsed whitespace)."""
    return " ".join(_clean_str(city).split()).lower()


def parse_cuisines(raw: Any) -> list[str]:
    if raw is None:
        return []
    s = _clean_str(raw)
    if not s:
        return []
    parts = re.split(r"[,|/]", s)
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        n = _normalize_cuisine_token(p)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def parse_rating(raw: Any) -> float | None:
    if raw is None:
        return None
    s = _clean_str(raw).upper()
    if not s or s == "NEW" or s == "-":
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    val = float(m.group(1))
    if val > 5.0:
        return None
    return val


def parse_approx_cost(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        if math.isnan(raw):
            return None
        return int(raw)
    s = _clean_str(str(raw))
    if not s:
        return None
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return None
    return int(digits)


def cost_band_from_inr(cost: int | None) -> str | None:
    if cost is None:
        return None
    if cost <= LOW_BAND_MAX_INR:
        return "low"
    if cost < HIGH_BAND_MIN_INR:
        return "medium"
    return "high"


def stable_restaurant_id(url: str, name: str, city: str, address: str) -> str:
    key = _clean_str(url)
    if not key:
        key = "|".join((_clean_str(name), _clean_str(city), _clean_str(address)))
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return digest[:32]


def _family_friendly_heuristic(rest_type: str, dish_liked: str, reviews_blob: Any) -> bool | None:
    blob = f"{rest_type} {dish_liked}".lower()
    if any(k in blob for k in _FAMILY_KEYWORDS):
        return True
    if reviews_blob is None:
        return None
    try:
        text = str(reviews_blob).lower()
    except Exception:
        return None
    if any(k in text for k in _FAMILY_KEYWORDS):
        return True
    return None


def _raw_field(raw: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in raw:
            return raw[k]
    return None


def transform_record(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map a single Hugging Face dataset row to the normalized schema.

    Expected HF column names (ManikaSaini/zomato-restaurant-recommendation).
    """
    name = _clean_str(_raw_field(raw, "name"))
    url = _clean_str(_raw_field(raw, "url"))
    address = _clean_str(_raw_field(raw, "address"))
    city = _clean_str(_raw_field(raw, "listed_in(city)"))
    area = _clean_str(_raw_field(raw, "location"))

    cost_raw = _raw_field(raw, "approx_cost(for two people)")
    approx = parse_approx_cost(cost_raw)
    band = cost_band_from_inr(approx)

    cuisines = parse_cuisines(_raw_field(raw, "cuisines"))
    rating = parse_rating(_raw_field(raw, "rate"))

    rest_type = _clean_str(_raw_field(raw, "rest_type"))
    dish_liked = _clean_str(_raw_field(raw, "dish_liked"))
    reviews_list = _raw_field(raw, "reviews_list")

    rid = stable_restaurant_id(url, name, city, address)
    family = _family_friendly_heuristic(rest_type, dish_liked, reviews_list)

    raw_notes_parts = [p for p in (rest_type, dish_liked) if p]
    raw_notes = "; ".join(raw_notes_parts)[:2000] if raw_notes_parts else None

    votes_raw = _raw_field(raw, "votes")
    votes: int | None = None
    if votes_raw is not None:
        try:
            votes = int(float(str(votes_raw).replace(",", "")))
        except (ValueError, TypeError):
            votes = None

    return {
        "restaurant_id": rid,
        "name": name,
        "city": city,
        "area": area or None,
        "cuisines": cuisines,
        "cost_band": band,
        "rating": rating,
        "approx_cost_for_two": approx,
        "votes": votes,
        "url": url or None,
        "address": address or None,
        "rest_type": rest_type or None,
        "tag_family_friendly": family,
        "raw_notes": raw_notes,
    }
