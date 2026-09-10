"""
State Overview (brief §33): for a state present in the cleaned data —
average / current AQI, districts & stations represented, best- and
worst-performing districts, the AQI-category distribution, and a monthly trend.
"""
from __future__ import annotations

import time
from statistics import mean

from backend.config.aqi_categories import AQI_CATEGORIES, categorize, category_meta
from backend.models import mongo_models as M
from backend.utils.responses import ApiError

_BUCKETS = [c["label"] for c in AQI_CATEGORIES]
_TTL = 300
_cache: dict[str, tuple[float, dict]] = {}


def _current_for(match: dict) -> dict | None:
    """Live CPCB mean for the match, else the latest historical station mean."""
    live = list(M.col("cpcb_live").aggregate([
        {"$match": {**match, "AQI": {"$ne": None}}},
        {"$group": {"_id": None, "aqi": {"$avg": "$AQI"}, "n": {"$sum": 1}}},
    ]))
    if live:
        v = round(live[0]["aqi"])
        return {"aqi": v, "bucket": categorize(v), "n_stations": live[0]["n"],
                "source": "live"}
    rows = list(M.col(M.AQI_RECORDS).find(
        {**match, "level": "station", "grain": "day", "AQI": {"$ne": None}},
        {"_id": 0, "AQI": 1, "date": 1}).sort("date", -1).limit(120))
    if not rows:
        return None
    latest = rows[0]["date"]
    vals = [r["AQI"] for r in rows if r["date"] == latest]
    v = round(mean(vals))
    return {"aqi": v, "bucket": categorize(v), "n_stations": len(vals),
            "source": "historical", "as_of": latest}


def _overview(state: str) -> dict:
    loc = M.col(M.LOCATIONS)
    if not loc.find_one({"state": state}):
        raise ApiError("unknown_state", f"No data for state '{state}'", 404)

    districts = sorted(d for d in loc.distinct("district", {"state": state}) if d)
    cities = sorted(c for c in loc.distinct("city", {"state": state}) if c)
    n_stations = len(loc.distinct("station_id", {"state": state,
                                                 "station_id": {"$ne": None}}))

    rec = M.col(M.AQI_RECORDS)
    base = {"state": state, "level": "station", "grain": "day",
            "AQI": {"$ne": None}}

    # --- averages ---
    agg = list(rec.aggregate([
        {"$match": base},
        {"$group": {"_id": None, "avg": {"$avg": "$AQI"},
                    "min": {"$min": "$AQI"}, "max": {"$max": "$AQI"},
                    "n": {"$sum": 1}, "first": {"$min": "$date"},
                    "last": {"$max": "$date"}}},
    ]))
    stats = agg[0] if agg else {}
    avg_aqi = round(stats["avg"]) if stats.get("avg") is not None else None

    # --- AQI category distribution ---
    dist = {b: 0 for b in _BUCKETS}
    for row in rec.aggregate([
        {"$match": {**base, "AQI_bucket": {"$in": _BUCKETS}}},
        {"$group": {"_id": "$AQI_bucket", "n": {"$sum": 1}}},
    ]):
        dist[row["_id"]] = row["n"]
    dist_total = sum(dist.values()) or 1
    distribution = [{"bucket": b, "count": dist[b],
                     "pct": round(100 * dist[b] / dist_total, 1),
                     "color": category_meta(b)["color"]} for b in _BUCKETS]

    # --- monthly trend (state-level mean) ---
    trend = [{"month": r["_id"], "aqi": round(r["avg"], 1), "n": r["n"]}
             for r in rec.aggregate([
                 {"$match": base},
                 {"$group": {"_id": {"$substr": ["$date", 0, 7]},
                             "avg": {"$avg": "$AQI"}, "n": {"$sum": 1}}},
                 {"$sort": {"_id": 1}},
             ])]

    # --- per-district rollup ---
    drows = []
    for d in districts:
        m = {"state": state, "district": d}
        da = list(rec.aggregate([
            {"$match": {**base, "district": d}},
            {"$group": {"_id": None, "avg": {"$avg": "$AQI"}, "n": {"$sum": 1}}},
        ]))
        avg = round(da[0]["avg"]) if da and da[0]["avg"] is not None else None
        cur = _current_for(m)
        drows.append({
            "district": d, "avg_aqi": avg,
            "avg_bucket": categorize(avg) if avg is not None else None,
            "current_aqi": cur["aqi"] if cur else None,
            "current_bucket": cur["bucket"] if cur else None,
            "n_stations": len(loc.distinct("station_id",
                              {"state": state, "district": d,
                               "station_id": {"$ne": None}})),
        })
    ranked = [r for r in drows if r["avg_aqi"] is not None]
    ranked.sort(key=lambda r: r["avg_aqi"])

    return {
        "state": state,
        "avg_aqi": avg_aqi,
        "avg_bucket": categorize(avg_aqi) if avg_aqi is not None else None,
        "current": _current_for({"state": state}),
        "n_districts": len(districts),
        "n_cities": len(cities),
        "n_stations": n_stations,
        "records": int(stats.get("n", 0)),
        "coverage": {"from": stats.get("first"), "to": stats.get("last"),
                     "aqi_min": stats.get("min"), "aqi_max": stats.get("max")},
        "distribution": distribution,
        "monthly_trend": trend,
        "districts": drows,
        "best_districts": ranked[:5],
        "worst_districts": list(reversed(ranked[-5:])),
        "cities": cities,
    }


def overview(state: str) -> dict:
    hit = _cache.get(state)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    val = _overview(state)
    _cache[state] = (time.time(), val)
    return val
