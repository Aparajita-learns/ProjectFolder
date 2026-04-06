# Data dictionary — processed restaurants (Phase 1)

**Source:** [ManikaSaini/zomato-restaurant-recommendation](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation) on Hugging Face.  
**Producer:** `phase1_ingestion/scripts/ingest.py` → `zomato_ingest.pipeline.run_ingest`  
**Artifact:** `data/processed/restaurants.parquet` (path overridable with env `DATA_PATH`)

## Row grain

One row per restaurant record from the source dataset after normalization (no deduplication unless added later).

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `restaurant_id` | string | no | SHA-256 (hex, 32 chars) of canonical URL, or of `name|city|address` if URL missing. Stable for LLM grounding. |
| `name` | string | no | Trimmed display name. |
| `city` | string | yes | From source `listed_in(city)` (area/city label in this dataset). |
| `area` | string | yes | Neighborhood/locality from source `location`. |
| `cuisines` | list of string | no | Lowercased tokens; multi-label split on comma/pipe/slash. |
| `cost_band` | string | yes | `low` / `medium` / `high` from INR **approx cost for two** (see rules below). Null if cost missing/unparsable. |
| `rating` | float | yes | Parsed from `rate` (e.g. `4.1/5`). Null for `NEW`, `-`, or unparsable. **Not imputed.** |
| `approx_cost_for_two` | int | yes | Numeric INR from `approx_cost(for two people)`. |
| `votes` | int | yes | Review vote count when parsable. |
| `url` | string | yes | Zomato URL when present. |
| `address` | string | yes | Full address string. |
| `rest_type` | string | yes | Restaurant type (e.g. Casual Dining). |
| `tag_family_friendly` | bool | yes | Heuristic: keywords *family*, *kid(s)*, *child* in `rest_type`, `dish_liked`, or `reviews_list`. Null if no signal. |
| `raw_notes` | string | yes | Truncated join of `rest_type` and `dish_liked` for future search (max 2000 chars). |

## Cost band rules (INR)

Thresholds are fixed (not dataset percentiles), documented in `zomato_ingest/transform.py`:

| Band | Condition (approx cost for two) |
|------|----------------------------------|
| `low` | ≤ 400 |
| `medium` | 401–1000 |
| `high` | > 1000 |

## Sidecar metadata

After each run, `restaurants.meta.json` next to the Parquet file records `dataset`, optional `revision`, output path, and a small `quality_report` (row counts, null shares, duplicate IDs).

---

## Phase 2 — SQLite query store

**Producer:** `phase2_query/scripts/materialize_sqlite.py` → `zomato_ingest.sqlite_store.materialize_sqlite`  
**Artifact:** `data/processed/restaurants.sqlite` (overridable with env `SQLITE_PATH`)

### Tables

- **`restaurants`** — One row per venue; mirrors Parquet scalars plus **`cuisines_json`** (JSON array string) for round-trip display.
- **`restaurant_cuisines`** — Junction `(restaurant_id, cuisine)` with one row per cuisine tag (lowercase), for indexed filters.

### Indexes

- `idx_restaurants_city_cost` on `(city, cost_band)`
- `idx_restaurants_city_rating` on `(city, rating)`
- `idx_restaurants_city` on `(city)`
- `idx_restaurant_cuisines_cuisine` on `(cuisine)`
- `idx_restaurant_cuisines_restaurant` on `(restaurant_id)`

### Query API

`zomato_ingest.query.filter_restaurants(conn, city=..., cuisines=..., cuisine_mode="any"|"all", min_rating=..., cost_bands=..., tag_family_friendly=..., limit=...)`

- **City:** strict match after `lower(trim(...))` on both sides (same normalization as `normalize_city_query` in `transform.py`).
- **Cuisines:** tokens normalized with `normalize_cuisine_query` (same synonym map as ingest). **`any`** = at least one overlap; **`all`** = restaurant must include every requested cuisine.
- **`min_rating`:** rows with NULL `rating` are excluded when this is set.
- **`cost_bands`:** when provided, rows with NULL `cost_band` are excluded.
