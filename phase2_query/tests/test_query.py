"""Phase 2 query and SQLite materialization tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from zomato_ingest.query import filter_restaurants
from zomato_ingest.sqlite_store import materialize_sqlite


@pytest.fixture()
def tiny_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame(
        [
            {
                "restaurant_id": "a1",
                "name": "A1",
                "city": "Delhi",
                "area": "CP",
                "cuisines": ["chinese", "thai"],
                "cost_band": "medium",
                "rating": 4.5,
                "approx_cost_for_two": 700,
                "votes": 100,
                "url": None,
                "address": None,
                "rest_type": None,
                "tag_family_friendly": True,
                "raw_notes": None,
            },
            {
                "restaurant_id": "a2",
                "name": "A2",
                "city": "Delhi",
                "area": None,
                "cuisines": ["italian"],
                "cost_band": "low",
                "rating": 3.0,
                "approx_cost_for_two": 300,
                "votes": 10,
                "url": None,
                "address": None,
                "rest_type": None,
                "tag_family_friendly": None,
                "raw_notes": None,
            },
            {
                "restaurant_id": "a3",
                "name": "A3",
                "city": "Delhi",
                "area": None,
                "cuisines": ["chinese", "north indian"],
                "cost_band": "high",
                "rating": None,
                "approx_cost_for_two": 1200,
                "votes": None,
                "url": None,
                "address": None,
                "rest_type": None,
                "tag_family_friendly": False,
                "raw_notes": None,
            },
            {
                "restaurant_id": "b1",
                "name": "B1",
                "city": "Mumbai",
                "area": None,
                "cuisines": ["chinese"],
                "cost_band": "medium",
                "rating": 4.0,
                "approx_cost_for_two": 600,
                "votes": 50,
                "url": None,
                "address": None,
                "rest_type": None,
                "tag_family_friendly": None,
                "raw_notes": None,
            },
        ]
    )
    df["rating"] = df["rating"].astype("Float64")
    df["approx_cost_for_two"] = df["approx_cost_for_two"].astype("Int64")
    df["votes"] = df["votes"].astype("Int64")
    df["tag_family_friendly"] = df["tag_family_friendly"].astype("boolean")
    p = tmp_path / "t.parquet"
    df.to_parquet(p, index=False)
    return p


@pytest.fixture()
def sqlite_conn(tiny_parquet: Path, tmp_path: Path):
    db = tmp_path / "t.sqlite"
    materialize_sqlite(tiny_parquet, db)
    import sqlite3

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_filter_wrong_city_empty(sqlite_conn):
    assert filter_restaurants(sqlite_conn, city="Chennai") == []


def test_filter_city_delhi_all_rows(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="delhi ")
    assert len(rows) == 3
    ids = {r["restaurant_id"] for r in rows}
    assert ids == {"a1", "a2", "a3"}


def test_min_rating_excludes_null(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="Delhi", min_rating=4.0)
    assert {r["restaurant_id"] for r in rows} == {"a1"}


def test_cost_bands_excludes_null_band(sqlite_conn):
    # a3 has high cost_band but null rating — still matches cost filter
    rows = filter_restaurants(sqlite_conn, city="Delhi", cost_bands=["high"])
    assert len(rows) == 1 and rows[0]["restaurant_id"] == "a3"


def test_cuisine_any(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="Delhi", cuisines=["Thai"])
    assert len(rows) == 1 and rows[0]["restaurant_id"] == "a1"


def test_cuisine_all(sqlite_conn):
    rows = filter_restaurants(
        sqlite_conn,
        city="Delhi",
        cuisines=["chinese", "north indian"],
        cuisine_mode="all",
    )
    assert len(rows) == 1 and rows[0]["restaurant_id"] == "a3"


def test_limit(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="Delhi", limit=2)
    assert len(rows) == 2


def test_family_tag_true(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="Delhi", tag_family_friendly=True)
    assert len(rows) == 1 and rows[0]["restaurant_id"] == "a1"


def test_row_roundtrip_cuisines_json(sqlite_conn):
    rows = filter_restaurants(sqlite_conn, city="Delhi", cuisines=["italian"])
    assert rows[0]["cuisines"] == ["italian"]


def test_materialize_junction_rows(tiny_parquet, tmp_path):
    db = tmp_path / "x.sqlite"
    materialize_sqlite(tiny_parquet, db)
    import sqlite3

    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM restaurant_cuisines").fetchone()[0]
    conn.close()
    # a1:2 + a2:1 + a3:2 + b1:1 = 6
    assert n == 6
