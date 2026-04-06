# Phase 2 — SQLite store and deterministic queries

**Shared library:** `src/zomato_ingest/` (`sqlite_store.py`, `query.py`)

| Path | Role |
|------|------|
| [`scripts/materialize_sqlite.py`](scripts/materialize_sqlite.py) | Parquet → SQLite + indexes |
| [`tests/test_query.py`](tests/test_query.py) | Filter and materialization tests |

**Run (from repo root, after Phase 1):**

```bash
python phase2_query/scripts/materialize_sqlite.py
```

Input/output default to `data/processed/restaurants.parquet` and `data/processed/restaurants.sqlite` (`DATA_PATH` / `SQLITE_PATH`).
