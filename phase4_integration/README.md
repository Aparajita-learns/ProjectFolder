# Phase 4 integration — tests + demo UI

- **`tests/test_phase4_backend.py`** — `build_llm_context` (empty list, Top-N + sort), mocked `POST /api/v1/recommend`.
- **`static/index.html`** — Basic single-page UI served by FastAPI at `/` (same origin as API).

Run the stack from the **repository root** (see root `README.md` for `uvicorn` + `PYTHONPATH=src`).
