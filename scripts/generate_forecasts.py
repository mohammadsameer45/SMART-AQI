"""
generate_forecasts.py  -  fill forecast_records for every eligible station.

Uses the trained best model + scalers to produce a recursive 7-day AQI forecast
for each station in data/processed/feature_table.parquet that has at least
SEQ_WINDOW+3 days of usable recent history, and upserts them into MongoDB.

Run after training:  python scripts/generate_forecasts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.ml.forecast import generate_all  # noqa: E402


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="only the first N eligible stations (smoke runs)")
    args = ap.parse_args()

    summary = generate_all(limit=args.limit)
    print(json.dumps(summary, indent=2))

    from backend.models import mongo_models as M
    total = M.col(M.FORECAST_RECORDS).estimated_document_count()
    stn = len(M.col(M.FORECAST_RECORDS).distinct("station_id"))
    print(f"\nforecast_records now holds {total} rows across {stn} stations "
          f"(model = {summary['model']})")


if __name__ == "__main__":
    main()
