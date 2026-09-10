"""Current AQI, history and pollutant analytics for a resolved area."""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from typing import Any

from backend.config.aqi_categories import categorize, category_meta
from backend.models import mongo_models as M
from backend.services.location_service import area_record_filter, resolve_area

POLLUTANTS = ["PM25", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3"]
_PROJ = {"_id": 0}


def _mean_by_date(rows: list[dict]) -> list[dict]:
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append(r)
    out = []
    for date, group in by_date.items():
        agg: dict[str, Any] = {"date": date, "ts": group[0]["ts"],
                               "level": "area_mean",
                               "state": group[0]["state"],
                               "city": group[0]["city"],
                               "n_stations": len(group)}
        for k in ["AQI"] + POLLUTANTS:
            vals = [g[k] for g in group if g.get(k) is not None]
            agg[k] = round(mean(vals), 2) if vals else None
        agg["AQI_display"] = None if agg["AQI"] is None else min(agg["AQI"], 500)
        agg["AQI_bucket"] = categorize(agg["AQI"])
        out.append(agg)
    return sorted(out, key=lambda d: d["date"])


def _pick_series_docs(resolved: dict, start=None, end=None) -> list[dict]:
    """Daily series for the area.

    * district match -> per-date mean of that district's stations
    * city match     -> the CPCB city-level daily series if we have it,
                        otherwise the per-date station mean
    Live (`grain="live"`) rows are excluded here; `history` is historical.
    """
    f = area_record_filter(resolved)
    if start or end:
        f["ts"] = {}
        if start:
            f["ts"]["$gte"] = start
        if end:
            f["ts"]["$lte"] = end

    if resolved["matched_level"] != "district":
        city = list(M.col(M.AQI_RECORDS)
                    .find(dict(f, level="city", grain="day"), _PROJ)
                    .sort("ts", 1))
        if city:
            return city
    rows = list(M.col(M.AQI_RECORDS)
                .find(dict(f, level="station", grain="day"), _PROJ)
                .sort("ts", 1))
    return _mean_by_date(rows)


def _live_current(resolved: dict) -> dict | None:
    """A fresh CPCB live reading for the area, if one exists (< 24 h old)."""
    f = area_record_filter(resolved)
    rows = list(M.col(M.AQI_RECORDS).find(dict(f, grain="live"), _PROJ)
                .sort("ts", -1))
    rows = [r for r in rows if r.get("AQI") is not None]
    if not rows:
        return None
    newest = rows[0]["ts"]
    fresh = [r for r in rows if newest - r["ts"] <= timedelta(hours=6)]
    aqis = [r["AQI"] for r in fresh]
    poll = {k: round(mean(v), 2) for k in POLLUTANTS
            if (v := [r[k] for r in fresh if r.get(k) is not None])}
    aqi = round(mean(aqis))
    return {
        "available": True,
        "as_of": newest.isoformat(),
        "is_live": True,
        "source_note": f"Live CPCB reading via data.gov.in "
                       f"(computed AQI, {len(fresh)} station(s)).",
        "matched_level": resolved["matched_level"],
        "AQI": aqi, "AQI_display": min(aqi, 500),
        "AQI_bucket": categorize(aqi), "category": category_meta(categorize(aqi)),
        "pollutants": {k: poll.get(k) for k in POLLUTANTS},
        "stations": [{"station": r["station"], "station_id": r.get("station_id"),
                      "AQI": r["AQI"], "AQI_bucket": r.get("AQI_bucket")}
                     for r in fresh],
    }


def current(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)

    live = _live_current(resolved)
    if live:
        return {**live, "state": state, "area": area}

    series = _pick_series_docs(resolved)
    if not series:
        return {"available": False,
                "reason": "No AQI records for this area."}
    latest = series[-1]
    aqi = latest.get("AQI")
    stn = list(M.col(M.AQI_RECORDS).find(
        {**area_record_filter(resolved), "level": "station",
         "date": latest["date"], "grain": "day"},
        {"_id": 0, "station_id": 1, "station": 1, "AQI": 1, "AQI_bucket": 1}))
    return {
        "available": True,
        "as_of": latest["date"],
        "is_live": False,
        "source_note": "Latest available historical value (Kaggle CPCB dataset "
                       "ends 2020-07-01; no fresh live reading for this area).",
        "state": state, "area": area,
        "matched_level": resolved["matched_level"],
        "AQI": aqi,
        "AQI_display": latest.get("AQI_display"),
        "AQI_bucket": latest.get("AQI_bucket"),
        "category": category_meta(latest.get("AQI_bucket")),
        "pollutants": {k: latest.get(k) for k in POLLUTANTS},
        "stations": stn,
    }


def history(state: str, area: str, frm: datetime | None, to: datetime | None,
            grain: str = "day") -> dict:
    resolved = resolve_area(state, area)
    series = _pick_series_docs(resolved, frm, to)
    keys = ["date", "AQI", "AQI_display", "AQI_bucket"] + POLLUTANTS
    return {
        "state": state, "area": area,
        "matched_level": resolved["matched_level"],
        "grain": grain,
        "count": len(series),
        "series": [{k: d.get(k) for k in keys} for d in series],
    }


def pollutants(state: str, area: str, trend_days: int = 30) -> dict:
    resolved = resolve_area(state, area)
    series = _pick_series_docs(resolved)
    if not series:
        return {"available": False, "reason": "No records for this area."}
    latest = series[-1]
    cutoff = latest["ts"] - timedelta(days=trend_days)
    window = [d for d in series if d["ts"] >= cutoff]
    health = {
        "PM25": "Fine particulate matter; penetrates deep into the lungs.",
        "PM10": "Coarse particulate matter; irritates airways.",
        "NO2": "Traffic-related gas; can inflame airways.",
        "SO2": "Combustion gas; can trigger bronchoconstriction.",
        "CO": "Reduces oxygen delivery in the blood.",
        "O3": "Ground-level ozone; irritant, worse on sunny days.",
        "NO": "Precursor to NO2 and ozone.",
        "NOx": "Nitrogen oxides, traffic/combustion related.",
        "NH3": "Ammonia; agricultural and waste sources.",
    }
    out = []
    for p in POLLUTANTS:
        vals = [d[p] for d in window if d.get(p) is not None]
        out.append({
            "pollutant": p,
            "current": latest.get(p),
            "unit": "mg/m³" if p == "CO" else "µg/m³",
            "trend_mean": round(mean(vals), 2) if vals else None,
            "trend_min": round(min(vals), 2) if vals else None,
            "trend_max": round(max(vals), 2) if vals else None,
            "n": len(vals),
            "health_relevance": health.get(p, ""),
        })
    return {"available": True, "as_of": latest["date"],
            "state": state, "area": area, "trend_days": trend_days,
            "pollutants": out}
