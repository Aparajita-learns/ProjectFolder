"""
Phase 2: materialize processed Parquet into SQLite with indexes and a cuisine junction table.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

DDL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS restaurant_cuisines;
DROP TABLE IF EXISTS restaurants;

CREATE TABLE restaurants (
    restaurant_id TEXT NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    area TEXT,
    cost_band TEXT,
    rating REAL,
    approx_cost_for_two INTEGER,
    votes INTEGER,
    url TEXT,
    address TEXT,
    rest_type TEXT,
    tag_family_friendly INTEGER,
    raw_notes TEXT,
    cuisines_json TEXT NOT NULL
);

CREATE INDEX idx_restaurants_city_cost ON restaurants (city, cost_band);
CREATE INDEX idx_restaurants_city_rating ON restaurants (city, rating);
CREATE INDEX idx_restaurants_city ON restaurants (city);

CREATE TABLE restaurant_cuisines (
    restaurant_id TEXT NOT NULL,
    cuisine TEXT NOT NULL,
    PRIMARY KEY (restaurant_id, cuisine),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants (restaurant_id) ON DELETE CASCADE
);

CREATE INDEX idx_restaurant_cuisines_cuisine ON restaurant_cuisines (cuisine);
CREATE INDEX idx_restaurant_cuisines_restaurant ON restaurant_cuisines (restaurant_id);
"""


def _coerce_cuisine_list(val: Any) -> list[str]:
    """Parquet/list columns may be list, ndarray, or None — never use ``or []`` on ndarrays."""
    if val is None:
        return []
    if hasattr(val, "tolist"):
        val = val.tolist()
    if isinstance(val, str):
        if not val.strip():
            return []
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                val = parsed
            else:
                return [str(parsed).strip().lower()]
        except json.JSONDecodeError:
            return [val.strip().lower()]
    if isinstance(val, (list, tuple)):
        out: list[str] = []
        for c in val:
            if c is None:
                continue
            s = str(c).strip().lower()
            if s:
                out.append(s)
        return out
    return []


def _bool_to_sql(v: Any) -> Any:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    # pandas nullable BooleanArray
    try:
        if pd.isna(v):
            return None
    except TypeError:
        pass
    return 1 if bool(v) else 0


def materialize_sqlite(parquet_path: Path, sqlite_path: Path, *, overwrite: bool = True) -> Path:
    """
    Build SQLite DB from Phase 1 Parquet: main row table + exploded cuisines for indexed filters.
    """
    parquet_path = Path(parquet_path)
    sqlite_path = Path(sqlite_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(parquet_path, engine="pyarrow")

    if overwrite and sqlite_path.exists():
        sqlite_path.unlink()

    conn = sqlite3.connect(str(sqlite_path))
    try:
        conn.executescript(DDL)

        rows: list[tuple[Any, ...]] = []
        cuisine_rows: list[tuple[str, str]] = []

        for rec in df.to_dict("records"):
            rid = rec["restaurant_id"]
            cuisines = _coerce_cuisine_list(rec.get("cuisines"))

            rows.append(
                (
                    rid,
                    rec["name"],
                    rec.get("city"),
                    rec.get("area"),
                    rec.get("cost_band"),
                    float(rec["rating"]) if rec.get("rating") is not None and pd.notna(rec.get("rating")) else None,
                    int(rec["approx_cost_for_two"])
                    if rec.get("approx_cost_for_two") is not None
                    and pd.notna(rec.get("approx_cost_for_two"))
                    else None,
                    int(rec["votes"]) if rec.get("votes") is not None and pd.notna(rec.get("votes")) else None,
                    rec.get("url"),
                    rec.get("address"),
                    rec.get("rest_type"),
                    _bool_to_sql(rec.get("tag_family_friendly")),
                    rec.get("raw_notes"),
                    json.dumps(cuisines),
                )
            )
            for c in cuisines:
                if isinstance(c, str) and c.strip():
                    cuisine_rows.append((rid, c.strip().lower()))

        conn.executemany(
            """
            INSERT INTO restaurants (
                restaurant_id, name, city, area, cost_band, rating,
                approx_cost_for_two, votes, url, address, rest_type,
                tag_family_friendly, raw_notes, cuisines_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO restaurant_cuisines (restaurant_id, cuisine) VALUES (?,?)",
            cuisine_rows,
        )
        conn.commit()
    finally:
        conn.close()

    return sqlite_path
