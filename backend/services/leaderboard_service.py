"""
National AQI leaderboard: ranks every district that actually has data
(real CPCB coverage via the existing district spatial join — the same
`locations.district` field the 3D map and District Explorer use), live
CPCB mean first, falling back to the latest historical station mean.
Nothing here is guessed; a district with no data simply doesn't appear.
"""
from __future__ import annotations

import time
from statistics import mean

from backend.config.aqi_categories import categorize, category_meta
from backend.models import mongo_models as M

_TTL = 300
_cache: dict[str, tuple[float, list]] = {}


def _current_for_district(state: str, district: str) -> dict | None:
    live = list(M.col("cpcb_live").aggregate([
        {"$match": {"state": state, "district": district, "AQI": {"$ne": None}}},
        {"$group": {"_id": None, "aqi": {"$avg": "$AQI"}, "n": {"$sum": 1}}},
    ]))
    if live:
        v = round(live[0]["aqi"])
        return {"aqi": v, "bucket": categorize(v), "n_stations": live[0]["n"],
                "source": "live"}
    rows = list(M.col(M.AQI_RECORDS).find(
        {"state": state, "district": district, "level": "station",
         "grain": "day", "AQI": {"$ne": None}},
        {"_id": 0, "AQI": 1, "date": 1}).sort("date", -1).limit(60))
    if not rows:
        return None
    latest = rows[0]["date"]
    vals = [r["AQI"] for r in rows if r["date"] == latest]
    v = round(mean(vals))
    return {"aqi": v, "bucket": categorize(v), "n_stations": len(vals),
            "source": "historical", "as_of": latest}


def _build() -> list[dict]:
    pairs = sorted({
        (d["state"], d["district"])
        for d in M.col(M.LOCATIONS).find(
            {"district": {"$ne": None}}, {"state": 1, "district": 1})
        if d.get("state") and d.get("district")
    })
    out = []
    for state, district in pairs:
        cur = _current_for_district(state, district)
        if not cur:
            continue
        out.append({
            "state": state, "district": district,
            "aqi": cur["aqi"], "bucket": cur["bucket"],
            "category": category_meta(cur["bucket"]),
            "n_stations": cur["n_stations"], "source": cur["source"],
        })
    out.sort(key=lambda r: r["aqi"])
    return out


def leaderboard(top_n: int = 10) -> dict:
    hit = _cache.get("all")
    if hit and time.time() - hit[0] < _TTL:
        rows = hit[1]
    else:
        rows = _build()
        _cache["all"] = (time.time(), rows)
    return {
        "generated_at": M.utcnow().isoformat(),
        "n_districts": len(rows),
        "best": rows[:top_n],
        "worst": list(reversed(rows[-top_n:])) if rows else [],
        "all": rows,
    }
