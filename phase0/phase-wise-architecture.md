# Phase-Wise Architecture: AI-Powered Restaurant Recommendation System

This document describes a phased architecture for the Zomato-inspired recommendation project defined in [`problemStatement.md`](problemStatement.md): data ingestion → user input → integration → LLM ranking → display.

For the **full** architecture (Groq, `.env`, detailed contracts), see [`../docs/phase-wise-architecture.md`](../docs/phase-wise-architecture.md).

---

## Phase 0 — Scope, constraints, and success criteria

**Goals:** Lock what “done” means before implementation.

- Define supported locations, budget bands, cuisines, and rating floors (match dataset reality).
- Choose LLM provider (OpenAI, Azure OpenAI, local, etc.), latency/cost limits, and whether explanations are required for every result.
- Decide deployment shape: local demo vs. hosted API + web UI.

**Outputs:** Short requirements doc, non-goals list, evaluation rubric (relevance, explanation quality, latency).

---

## Phase 1 — Data foundation (ingestion & preprocessing)

**Goals:** Reliable access to structured restaurant records.

| Layer | Responsibility |
|--------|----------------|
| **Source** | Hugging Face dataset [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) |
| **Ingestion** | Script or job: download, version pin, parse into a normalized schema |
| **Cleaning** | Handle nulls, unify cuisine strings, map cost to low/medium/high, normalize city/area names |
| **Schema** | Core fields: name, location, cuisine(s), cost/price band, rating, optional tags (family-friendly, etc. if derivable) |

**Outputs:** Cleaned tabular store (CSV/Parquet/SQLite/Postgres) + data dictionary; optional small “golden” test set for regression.

---

## Phase 2 — Storage & query layer

**Goals:** Fast filtering for the integration layer.

- **Index** restaurants by: location, cuisine, rating ≥ threshold, cost band.
- **Search** (optional later): text search on name/cuisine for “additional preferences.”

**Outputs:** Query module/API (e.g. `filter_restaurants(prefs) -> DataFrame/list`) with unit tests on edge cases (empty results, strict filters).

---

## Phase 3 — User input & preference model

**Goals:** Capture and validate what the workflow calls “user preferences.”

- **Input channels:** Form (web) or JSON API body.
- **Model:** Structured object: `location`, `budget`, `cuisine`, `min_rating`, `free_text_notes` (family-friendly, quick service, etc.).
- **Validation:** Reject or coerce invalid enums; cap free-text length for prompt safety.

**Outputs:** Pydantic models / TypeScript types + validation errors surfaced clearly to the UI.

---

## Phase 4 — Integration layer (filter → LLM context)

**Goals:** “Filter and prepare relevant restaurant data” and “pass structured results into an LLM prompt.”
```mermaid
flowchart LR
  subgraph inputs [User prefs]
    P[Preferences]
  end
  subgraph data [Data layer]
    DB[(Restaurant store)]
  end
  subgraph integration [Integration layer]
    F[Deterministic filter]
    S[Candidate selector Top N]
    J[JSON context builder]
  end
  subgraph llm [LLM]
    L[Rank + explain]
  end
  P --> F
  DB --> F
  F --> S
  S --> J
  J --> L
```

- **Deterministic filter:** Apply location, budget, cuisine, min rating (and any rule-based tags).
- **Candidate cap:** Pass top *N* (e.g. 15–30) to the LLM to control tokens and cost; tie-break with rating/cost proximity.
- **Context pack:** Compact JSON or bullet list per candidate (name, cuisine, rating, cost, location snippet).

**Outputs:** `build_llm_context(user_prefs, candidates)` with logging of filter counts (before/after).

---

## Phase 5 — Recommendation engine (LLM)

**Goals:** Rank, explain, optionally summarize per the problem statement.

- **Prompt design:** System + user messages: role (expert recommender), rules (only from provided list, no invented restaurants), output format (JSON or structured markdown).
- **Post-processing:** Parse LLM output; validate restaurant IDs/names against candidates; fallback ranking if parse fails (e.g. sort by rating).
- **Optional:** Short summary paragraph of the whole set of picks.

**Outputs:** Versioned prompts, temperature/max-tokens config, golden-prompt tests.

---

## Phase 6 — Application & presentation layer

**Goals:** “Display clear and useful results” end-to-end.

| Piece | Role |
|--------|------|
| **Backend** | REST (or similar): `POST /recommend` accepts prefs → returns ranked list + explanations |
| **Frontend** | Cards/table: Name, Cuisine, Rating, Estimated Cost, AI explanation |
| **UX** | Loading state, empty state (“no matches — relax filters”), error state (LLM/API down) |

**Outputs:** Runnable app (e.g. FastAPI + simple React/Streamlit — pick one stack and stay consistent).

---

## Phase 7 — Hardening & operations

**Goals:** Safe, observable, repeatable runs.

- **Safety:** Prompt injection mitigations on free-text; rate limiting if public.
- **Observability:** Log request id, filter sizes, LLM latency, token usage (if available).
- **Config:** Env-based API keys, dataset path, model name.

**Outputs:** README with setup steps, `.env.example`, minimal CI (lint/tests) if you use a repo.

---

## Suggested build order (dependency-aware)

1. Phase 0 → 1 → 2 (data path must work first).
2. Phase 3 + 4 in parallel once filtering exists.
3. Phase 5 after Phase 4 produces stable context.
4. Phase 6 wires UI/API.
5. Phase 7 before any demo or share-out.

---

## One-line architecture summary

**Deterministic filtering** over a preprocessed Zomato-derived store selects a bounded candidate set; an **integration layer** formats that set for the **LLM**, which **ranks and explains**; the **API/UI** returns structured results with explanations and strict validation so the model cannot fabricate restaurants outside the provided list.
