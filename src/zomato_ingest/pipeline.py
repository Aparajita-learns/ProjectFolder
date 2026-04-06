"""Load HF dataset, normalize rows, assert quality gates, write Parquet."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import load_dataset

from zomato_ingest.transform import transform_record

logger = logging.getLogger(__name__)

DATASET_NAME = "ManikaSaini/zomato-restaurant-recommendation"


def _quality_report(df: pd.DataFrame) -> dict[str, Any]:
    n = len(df)
    return {
        "row_count": n,
        "share_with_rating": float(df["rating"].notna().mean()) if n else 0.0,
        "share_with_cost_band": float(df["cost_band"].notna().mean()) if n else 0.0,
        "share_with_city": float(df["city"].astype(str).str.len().gt(0).mean()) if n else 0.0,
        "duplicate_restaurant_ids": int(df["restaurant_id"].duplicated().sum()),
        "unique_cities": int(df["city"].nunique()),
    }


def run_ingest(
    output_parquet: Path,
    *,
    revision: str | None = None,
    limit: int | None = None,
    dataset_name: str = DATASET_NAME,
) -> dict[str, Any]:
    """
    Download/load dataset, transform, run assertions, write Parquet.

    Returns a dict with paths and quality_report.
    """
    output_parquet = Path(output_parquet)
    output_parquet.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict[str, Any] = {}
    if revision:
        kwargs["revision"] = revision

    logger.info("Loading dataset %s (revision=%s)", dataset_name, revision or "default")
    ds = load_dataset(dataset_name, split="train", **kwargs)
    df_raw = ds.to_pandas()
    if limit is not None:
        df_raw = df_raw.head(limit)

    records = df_raw.to_dict("records")
    normalized = [transform_record(dict(r)) for r in records]
    df = pd.DataFrame(normalized)

    df["rating"] = df["rating"].astype("Float64")
    df["approx_cost_for_two"] = df["approx_cost_for_two"].astype("Int64")
    df["votes"] = df["votes"].astype("Int64")
    df["tag_family_friendly"] = df["tag_family_friendly"].astype("boolean")

    # --- Quality gates (Phase 1) ---
    n = len(df)
    if n == 0:
        raise ValueError("Ingest produced zero rows; check dataset access and filters.")

    if df["restaurant_id"].isna().any() or (df["restaurant_id"].astype(str).str.len() == 0).any():
        raise ValueError("Quality gate failed: missing restaurant_id.")

    if (df["name"].astype(str).str.strip().str.len() == 0).mean() > 0.05:
        logger.warning("More than 5%% of rows have empty name; review source data.")

    report = _quality_report(df)
    logger.info("Quality report: %s", json.dumps(report, indent=2))

    df.to_parquet(output_parquet, index=False, engine="pyarrow")

    meta_path = output_parquet.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "dataset": dataset_name,
                "revision": revision,
                "output_parquet": str(output_parquet.resolve()),
                "quality_report": report,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "output_parquet": str(output_parquet.resolve()),
        "meta_path": str(meta_path.resolve()),
        "quality_report": report,
    }


def default_output_path() -> Path:
    raw = os.environ.get("DATA_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data" / "processed" / "restaurants.parquet"
