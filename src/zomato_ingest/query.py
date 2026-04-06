"""
Phase 2: deterministic restaurant filters over SQLite (no LLM).

Cuisine filter semantics (documented):
  - ``cuisine_mode="any"`` (default): keep rows that have at least one of the requested cuisines.
  - ``cuisine_mode="all"``: keep rows whose cuisines are a superset of the requested list.

City match: strict normalized equality on ``restaurants.city`` (case-insensitive, trimmed whitespace).

When ``min_rating`` is set, rows with NULL rating are excluded.
When ``cost_bands`` is non-empty, rows with NULL ``cost_band`` are excluded.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Literal

from zomato_ingest.transform import normalize_city_query, normalize_cuisine_query

CuisineMode = Literal["any", "all"]


def default_sqlite_path() -> Path:
    raw = os.environ.get("SQLITE_PATH", "").strip()
    if raw:
        return Path(raw)
    base = Path(__file__).resolve().parents[2] / "data" / "processed"
    return base / "restaurants.sqlite"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else default_sqlite_path()
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    raw_ff = d.get("tag_family_friendly")
    if raw_ff is None:
        d["tag_family_friendly"] = None
    else:
        d["tag_family_friendly"] = bool(raw_ff)
    cj = d.pop("cuisines_json", "[]")
    try:
        d["cuisines"] = json.loads(cj) if isinstance(cj, str) else list(cj)
    except json.JSONDecodeError:
        d["cuisines"] = []
    return d


def filter_restaurants(
    conn: sqlite3.Connection,
    *,
    city: str,
    cuisines: list[str] | None = None,
    cuisine_mode: CuisineMode = "any",
    min_rating: float | None = None,
    cost_bands: list[str] | None = None,
    tag_family_friendly: bool | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Return matching restaurants as dicts (including ``cuisines`` as a list of strings).

    ``limit`` caps result count (safety before Top-N for LLM). ``None`` means no cap.
    """
    city_key = normalize_city_query(city)
    if not city_key:
        return []

    where = ["lower(trim(ifnull(r.city,''))) = ?"]
    params: list[Any] = [city_key]

    if min_rating is not None:
        where.append("r.rating IS NOT NULL AND r.rating >= ?")
        params.append(min_rating)

    if cost_bands:
        placeholders = ",".join("?" * len(cost_bands))
        where.append(f"r.cost_band IS NOT NULL AND r.cost_band IN ({placeholders})")
        params.extend(cost_bands)

    if tag_family_friendly is True:
        where.append("r.tag_family_friendly = 1")
    elif tag_family_friendly is False:
        where.append("(r.tag_family_friendly = 0 OR r.tag_family_friendly IS NULL)")

    norm_cuisines: list[str] = []
    if cuisines:
        for c in cuisines:
            n = normalize_cuisine_query(c)
            if n and n not in norm_cuisines:
                norm_cuisines.append(n)

    join_sql = ""
    if norm_cuisines:
        ph = ",".join("?" * len(norm_cuisines))
        if cuisine_mode == "any":
            join_sql = f"""
            AND EXISTS (
                SELECT 1 FROM restaurant_cuisines rc
                WHERE rc.restaurant_id = r.restaurant_id AND rc.cuisine IN ({ph})
            )
            """
            params.extend(norm_cuisines)
        else:
            join_sql = f"""
            AND (
                SELECT COUNT(DISTINCT rc.cuisine) FROM restaurant_cuisines rc
                WHERE rc.restaurant_id = r.restaurant_id AND rc.cuisine IN ({ph})
            ) = ?
            """
            params.extend(norm_cuisines)
            params.append(len(norm_cuisines))

    sql = f"""
        SELECT r.* FROM restaurants r
        WHERE {" AND ".join(where)}
        {join_sql}
        ORDER BY r.rating IS NULL, r.rating DESC, r.votes IS NULL, r.votes DESC
    """
    if limit is not None:
        sql += f" LIMIT {int(limit)}"

    cur = conn.execute(sql, params)
    return [_row_to_dict(row) for row in cur.fetchall()]
