# Phase 1 — Data ingestion and normalization

**Shared library:** `src/zomato_ingest/` (`transform.py`, `pipeline.py`)

| Path | Role |
|------|------|
| [`scripts/ingest.py`](scripts/ingest.py) | CLI: HF dataset → Parquet |
| [`tests/test_transform.py`](tests/test_transform.py) | Golden tests for normalization |
| [`../docs/data_dictionary.md`](../docs/data_dictionary.md) | Schema and cost-band rules |

**Run (from repo root):**

```bash
pip install -r requirements.txt
python phase1_ingestion/scripts/ingest.py
```

Output defaults to `data/processed/restaurants.parquet` (override with `DATA_PATH`).
