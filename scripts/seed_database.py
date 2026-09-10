"""
seed_database.py  -  Phase 6 MongoDB seed for SMART AQI.

Loads the cleaned DAILY tables into a local MongoDB (`smart_aqi`):

  locations          one row per monitoring city and per station, with the
                     history window and record counts actually present
  aqi_records        cleaned city-day and station-day observations
  health_advisories  baseline CPCB-category advisory content
  forecast_records   created empty (populated by the training pipeline)
  model_metrics      created empty (populated by the training pipeline)

Hourly data is intentionally NOT seeded - it stays in data/cleaned/ for the ML
pipeline (see docs/architecture.md section 4).

Idempotent: every document has a deterministic _id and is upserted, so the
script is safe to run repeatedly without creating duplicates.

Usage:
  python scripts/seed_database.py            # seed everything
  python scripts/seed_database.py --drop     # drop smart_aqi collections first
  python scripts/seed_database.py --only aqi_records,locations
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from pymongo import ReplaceOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config.aqi_categories import categorize  # noqa: E402
from backend.config.health_advisories_seed import ADVISORIES  # noqa: E402
from backend.models import mongo_models as M  # noqa: E402

CLEAN = ROOT / "data" / "cleaned"
DAILY_FILES = [("city_day.csv.gz", "city"), ("station_day.csv.gz", "station")]
POLLUTANTS = ["PM25", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3",
              "Benzene", "Toluene", "Xylene"]
BATCH = 2000


def _num(v):
    """pandas/NumPy scalar -> plain float or None (never NaN)."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _load_daily() -> pd.DataFrame:
    frames = []
    for fname, level in DAILY_FILES:
        df = pd.read_csv(CLEAN / fname, low_memory=False)
        df["level"] = level
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["date"], utc=True)
    return df


# ------------------------------------------------------------------ locations
def seed_locations(df: pd.DataFrame) -> int:
    ops = []
    # city-level rows
    city = df[df.level == "city"]
    for (state, cty), g in city.groupby(["state", "city"], dropna=False):
        _id = f"city:{state}|{cty}"
        ops.append(ReplaceOne({"_id": _id}, {
            "_id": _id, "level": "city", "state": state, "city": cty,
            "district": None, "station": None, "station_id": None,
            "lat": None, "lon": None,
            "grains": ["day"], "grains_available": ["day", "hour"],
            "sources": sorted(g["source"].unique().tolist()),
            "has_history": True,
            "history_start": g["date"].min(), "history_end": g["date"].max(),
            "n_records": int(len(g)),
            "updated_at": M.utcnow(),
        }, upsert=True))
    # station-level rows
    stn = df[df.level == "station"]
    for sid, g in stn.groupby("station_id", dropna=True):
        _id = f"station:{sid}"
        r0 = g.iloc[0]
        ops.append(ReplaceOne({"_id": _id}, {
            "_id": _id, "level": "station", "state": r0["state"],
            "city": r0["city"], "district": None,
            "station": r0["station"], "station_id": sid,
            "lat": None, "lon": None,
            "grains": ["day"], "grains_available": ["day", "hour"],
            "sources": sorted(g["source"].unique().tolist()),
            "has_history": True,
            "history_start": g["date"].min(), "history_end": g["date"].max(),
            "n_records": int(len(g)),
            "updated_at": M.utcnow(),
        }, upsert=True))
    return _bulk(M.LOCATIONS, ops)


# ---------------------------------------------------------------- aqi_records
def seed_aqi_records(df: pd.DataFrame) -> int:
    total = 0
    ops: list[ReplaceOne] = []
    cols = df.columns
    for row in df.itertuples(index=False):
        d = dict(zip(cols, row))
        key = d["station_id"] if (isinstance(d["station_id"], str) and d["station_id"]) \
            else d["city"]
        _id = f'{d["source"]}:{key}:{d["date"]}'
        aqi = _num(d["AQI"])
        ts: datetime = d["ts"].to_pydatetime()
        doc = {
            "_id": _id, "level": d["level"],
            "state": d["state"], "city": d["city"], "district": None,
            "station": d["station"] if isinstance(d["station"], str) else None,
            "station_id": key if d["level"] == "station" else None,
            "date": d["date"], "ts": ts, "grain": "day",
            "year": ts.year, "month": ts.month,
            "AQI": aqi,
            "AQI_display": None if aqi is None else min(aqi, 500.0),
            "AQI_bucket": d["AQI_bucket"] if isinstance(d["AQI_bucket"], str)
            else categorize(aqi),
            "source": d["source"],
            "ingested_at": str(d["ingested_at"]),
        }
        for p in POLLUTANTS:
            doc[p] = _num(d[p])
        ops.append(ReplaceOne({"_id": _id}, doc, upsert=True))
        if len(ops) >= BATCH:
            total += _bulk(M.AQI_RECORDS, ops)
            ops = []
    total += _bulk(M.AQI_RECORDS, ops)
    return total


# ----------------------------------------------------------- health_advisories
def seed_health_advisories() -> int:
    ops = []
    for a in ADVISORIES:
        _id = f'{a["aqi_bucket"]}:{a["audience"]}'
        ops.append(ReplaceOne({"_id": _id},
                              {"_id": _id, **a, "updated_at": M.utcnow()},
                              upsert=True))
    return _bulk(M.HEALTH_ADVISORIES, ops)


# --------------------------------------------------------------------- helpers
def _bulk(coll_name: str, ops: list) -> int:
    if not ops:
        return 0
    res = M.col(coll_name).bulk_write(ops, ordered=False)
    # documents actually created or changed (unchanged re-seeds report 0)
    return (res.upserted_count or 0) + (res.modified_count or 0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true",
                    help="drop smart_aqi collections before seeding")
    ap.add_argument("--only", default="",
                    help="comma list: locations,aqi_records,health_advisories")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    print(f"MongoDB {M.ping()}  ->  db '{M.get_db().name}'")

    if args.drop:
        for c in M.ALL_COLLECTIONS:
            M.get_db().drop_collection(c)
        print("dropped:", ", ".join(M.ALL_COLLECTIONS))

    # make sure empty collections exist so Compass shows them
    existing = set(M.get_db().list_collection_names())
    for c in M.ALL_COLLECTIONS:
        if c not in existing:
            M.get_db().create_collection(c)

    print("creating indexes ...")
    idx = M.ensure_indexes()
    for c, names in idx.items():
        print(f"  {c}: {', '.join(names)}")

    df = None
    if not only or {"locations", "aqi_records"} & only:
        print("loading cleaned daily data ...")
        df = _load_daily()
        print(f"  {len(df):,} daily rows "
              f"({(df.level == 'city').sum():,} city / "
              f"{(df.level == 'station').sum():,} station)")

    if not only or "locations" in only:
        n = seed_locations(df)
        print(f"locations       upserted/matched: {n:,} "
              f"(total in db: {M.col(M.LOCATIONS).estimated_document_count():,})")

    if not only or "aqi_records" in only:
        n = seed_aqi_records(df)
        print(f"aqi_records      upserted/matched: {n:,} "
              f"(total in db: {M.col(M.AQI_RECORDS).estimated_document_count():,})")

    if not only or "health_advisories" in only:
        n = seed_health_advisories()
        print(f"health_advisories upserted/matched: {n:,} "
              f"(total in db: {M.col(M.HEALTH_ADVISORIES).estimated_document_count():,})")

    print("\ndone.")


if __name__ == "__main__":
    main()
