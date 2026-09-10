"""
ingest_cpcb_live.py  -  pull the CPCB real-time AQI feed (data.gov.in) and:

  1. write data/metadata/cpcb_stations.json   (station master + coordinates)
  2. upsert the current reading per station into aqi_records
     (source="cpcb_live", grain="live")
  3. refresh a `cpcb_live` collection (latest snapshot, easy to inspect)
  4. fill lat/lon on matching `locations`

Coordinates from step 1 feed scripts/build_station_districts.py.

Run:  python scripts/ingest_cpcb_live.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pymongo import ASCENDING, ReplaceOne  # noqa: E402

from backend.config.aqi_categories import categorize  # noqa: E402
from backend.models import mongo_models as M  # noqa: E402
from backend.services.datagovin import stations  # noqa: E402

META = ROOT / "data" / "metadata"
POLLUTANTS = ["PM25", "PM10", "NO2", "SO2", "CO", "O3", "NH3"]


def _norm(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def main() -> None:
    print("fetching CPCB live feed from data.gov.in ...")
    stns = stations()
    with_coords = [s for s in stns if s["lat"] and s["lon"]]
    with_aqi = [s for s in stns if s["AQI"] is not None]
    print(f"  {len(stns)} stations  |  {len(with_coords)} geolocated  |  "
          f"{len(with_aqi)} with a computable AQI")

    META.mkdir(parents=True, exist_ok=True)
    (META / "cpcb_stations.json").write_text(json.dumps([
        {k: s[k] for k in ("station", "state", "city", "lat", "lon",
                           "last_update", "AQI", "pollutants")}
        for s in stns
    ], indent=2, default=str), encoding="utf-8")
    print(f"  wrote {META / 'cpcb_stations.json'}")

    # --- cpcb_live snapshot collection ---
    M.get_db().drop_collection("cpcb_live")
    live_docs = []
    for s in stns:
        live_docs.append({
            "_id": s["station"],
            "state": s["state"], "city": s["city"],
            "lat": s["lat"], "lon": s["lon"],
            "last_update": s["last_update"], "ts": s["ts"],
            "AQI": s["AQI"], "AQI_bucket": categorize(s["AQI"]),
            "AQI_subindices": s["AQI_subindices"], "AQI_note": s["AQI_note"],
            **{p: s["pollutants"].get(p) for p in POLLUTANTS},
            "source": "cpcb_live",
        })
    if live_docs:
        M.col("cpcb_live").insert_many(live_docs)
        M.col("cpcb_live").create_index([("state", ASCENDING), ("city", ASCENDING)])
        M.col("cpcb_live").create_index([("ts", ASCENDING)])
    print(f"  cpcb_live collection: {len(live_docs)} docs")

    # name -> historical station master (so live rows join to the same areas)
    name_to_loc = {}
    for d in M.col(M.LOCATIONS).find(
            {"level": "station"}, {"station": 1, "station_id": 1, "city": 1}):
        if d.get("station"):
            name_to_loc[_norm(d["station"])] = d

    # --- upsert current readings into aqi_records ---
    ops = []
    for s in stns:
        if s["ts"] is None:
            continue
        loc = name_to_loc.get(_norm(s["station"]))
        _id = f'cpcb_live:{s["station"]}:{s["ts"].strftime("%Y-%m-%dT%H:%M")}'
        ops.append(ReplaceOne({"_id": _id}, {
            "_id": _id, "level": "station",
            "state": s["state"],
            "city": loc["city"] if loc else s["city"],
            "district": None,
            "station": s["station"],
            "station_id": loc["station_id"] if loc else None,
            "date": s["ts"].strftime("%Y-%m-%d"), "ts": s["ts"],
            "grain": "live", "year": s["ts"].year, "month": s["ts"].month,
            "AQI": s["AQI"],
            "AQI_display": None if s["AQI"] is None else min(s["AQI"], 500),
            "AQI_bucket": categorize(s["AQI"]),
            **{p: s["pollutants"].get(p) for p in POLLUTANTS},
            "PM10": s["pollutants"].get("PM10"),
            "source": "cpcb_live",
            "ingested_at": M.utcnow(),
        }, upsert=True))
    if ops:
        for i in range(0, len(ops), 500):
            M.col(M.AQI_RECORDS).bulk_write(ops[i:i + 500], ordered=False)
    print(f"  aqi_records: upserted {len(ops)} live readings")

    # --- fill lat/lon on matching locations (by station name) ---
    loc_by_name = {}
    for d in M.col(M.LOCATIONS).find({"level": "station"}, {"station": 1}):
        if d.get("station"):
            loc_by_name[_norm(d["station"])] = d["_id"]
    matched = 0
    for s in stns:
        _id = loc_by_name.get(_norm(s["station"]))
        if _id and s["lat"] and s["lon"]:
            M.col(M.LOCATIONS).update_one(
                {"_id": _id}, {"$set": {"lat": s["lat"], "lon": s["lon"]}})
            matched += 1
    print(f"  locations: set coordinates on {matched} stations "
          f"(matched to the historical station master by name)")

    print("\ndone.")


if __name__ == "__main__":
    main()
