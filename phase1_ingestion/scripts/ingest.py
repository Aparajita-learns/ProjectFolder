#!/usr/bin/env python3
"""
Phase 1: download Zomato HF dataset, normalize, write Parquet.

Usage (from repository root):
  python phase1_ingestion/scripts/ingest.py
  python phase1_ingestion/scripts/ingest.py --revision main --limit 500
  set DATA_PATH=out\\zomato.parquet && python phase1_ingestion/scripts/ingest.py

Requires: pip install -r requirements.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Repository root (parent of phase1_ingestion/)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from zomato_ingest.pipeline import default_output_path, run_ingest  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Ingest Zomato HF dataset to Parquet (Phase 1).")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output Parquet path (default: DATA_PATH env or data/processed/restaurants.parquet)",
    )
    p.add_argument(
        "--revision",
        default=None,
        help="Hugging Face dataset revision (git ref) for reproducibility.",
    )
    p.add_argument("--limit", type=int, default=None, help="Process only first N rows (dev/test).")
    args = p.parse_args()
    out = args.output or default_output_path()
    result = run_ingest(out, revision=args.revision, limit=args.limit)
    logging.info("Wrote %s", result["output_parquet"])
    logging.info("Metadata %s", result["meta_path"])


if __name__ == "__main__":
    main()
