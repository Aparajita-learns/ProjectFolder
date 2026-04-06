# Restaurant recommendation (Zomato-style) — phased layout

| Folder | Phase | Contents |
|--------|-------|----------|
| [`phase0/`](phase0/) | 0 | Problem statement, short architecture, links to full docs |
| [`phase1_ingestion/`](phase1_ingestion/) | 1 | `scripts/ingest.py`, `tests/test_transform.py` |
| [`phase2_query/`](phase2_query/) | 2 | `scripts/materialize_sqlite.py`, `tests/test_query.py` |
| [`docs/`](docs/) | — | Detailed architecture, data dictionary |
| [`phase4_integration/`](phase4_integration/) | 4–6 | Tests + static demo UI (`static/index.html`) |
| [`phase5_llm/tests/`](phase5_llm/tests/) | 5 | Groq connectivity tests (`GROQ_API_KEY` in `.env`) |
| [`src/zomato_recommend/`](src/zomato_recommend/) | 3–6 | Pydantic prefs, Phase 4 context, Groq rank, FastAPI |
| [`src/zomato_ingest/`](src/zomato_ingest/) | 1–2 | Shared Python package (transform, pipeline, SQLite, query) |
| [`data/processed/`](data/processed/) | — | Generated Parquet / SQLite (often gitignored) |

**Run from repository root:**

```bash
pip install -r requirements.txt
python phase1_ingestion/scripts/ingest.py
python phase2_query/scripts/materialize_sqlite.py
python -m pytest -q
```

**Demo API + UI (after ingest, materialize, and `.env` with `GROQ_API_KEY`):**

```bash
# Easiest (no PYTHONPATH): from repo root, leave this terminal open
python run_dev.py
```

Or: `.\run_server.ps1` in PowerShell.

Then open **[http://127.0.0.1:8765](http://127.0.0.1:8765)** — not `https://`.

**ERR_CONNECTION_REFUSED** usually means (1) the server is not running — run `python run_dev.py` and **leave that terminal open**, or (2) Windows blocked port 8000 — this project defaults to **8765** to avoid that. Override with `$env:PORT = "8080"; python run_dev.py` if needed.

Alternate: `$env:PYTHONPATH = "src"; python -m uvicorn zomato_recommend.app:app --reload --host 127.0.0.1 --port 8765`

Endpoints: `GET /health`, `POST /api/v1/recommend`.

Secrets: copy `.env.example` → `.env` and set **`GROQ_API_KEY`**. See `docs/phase-wise-architecture.md`.
