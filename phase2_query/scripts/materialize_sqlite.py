#!/usr/bin/env python3
"""
Phase 2: build SQLite from Phase 1 Parquet (indexes + cuisine junction table).

Usage (from repository root):
  python phase2_query/scripts/materialize_sqlite.py
  python phase2_query/scripts/materialize_sqlite.py -i data/processed/restaurants.parquet -o data/processed/restaurants.sqlite

Input path: DATA_PATH env or default Parquet from Phase 1.
Output path: SQLITE_PATH env or data/processed/restaurants.sqlite.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from zomato_ingest.pipeline import default_output_path  # noqa: E402
from zomato_ingest.query import default_sqlite_path  # noqa: E402
from zomato_ingest.sqlite_store import materialize_sqlite  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Materialize Parquet → SQLite for Phase 2 queries.")
    p.add_argument("-i", "--input", type=Path, default=None, help="Input Parquet (default: DATA_PATH / Phase 1 default).")
    p.add_argument("-o", "--output", type=Path, default=None, help="Output SQLite (default: SQLITE_PATH / data/processed/restaurants.sqlite).")
    args = p.parse_args()
    inp = args.input or default_output_path()
    out = args.output or default_sqlite_path()
    if not inp.exists():
        logging.error("Parquet not found: %s — run phase1_ingestion/scripts/ingest.py first.", inp)
        sys.exit(1)
    materialize_sqlite(inp, out)
    logging.info("Wrote %s", out.resolve())


if __name__ == "__main__":
    main()
