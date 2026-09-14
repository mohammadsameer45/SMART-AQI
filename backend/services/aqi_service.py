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

# The CPCB real-time (data.gov.in) feed only ever publishes these seven - NO
# and NOx are not sent by the live resource at all (verified against the raw
# feed), only present in the 2015-2020 historical dataset. Kept in sync with
# scripts/ingest_cpcb_live.py's own POLLUTANTS list.
LIVE_PUBLISHED_POLLUTANTS = {"PM25", "PM10", "NO2", "SO2", "CO", "O3", "NH3"}

# General source categories a pollutant is typically associated with - not a
# claim about the cause of any specific reading. Used for the pollutant-detail
# cards and as the evidence-free half of the source-analysis ranking.
POLLUTANT_SOURCE_HINTS: dict[str, list[str]] = {
    "PM25": ["Traffic", "Construction/dust", "Biomass burning",
             "Industrial emissions", "Atmospheric conditions (stagnation)"],
    "PM10": ["Construction/dust", "Traffic", "Industrial emissions",
             "Atmospheric conditions (stagnation)"],
    "NO2": ["Traffic", "Industrial emissions"],
    "NO": ["Traffic", "Industrial emissions"],
    "NOx": ["Traffic", "Industrial emissions"],
    "SO2": ["Industrial emissions", "Combustion (power plants, diesel gensets)"],
    "CO": ["Traffic", "Biomass burning", "Incomplete combustion"],
    "O3": ["Atmospheric chemistry (sunlight + precursor pollutants)",
           "Not directly emitted - a secondary pollutant"],
    "NH3": ["Agricultural activity", "Waste/sewage", "Industrial emissions"],
}


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


def _area_live_series(resolved: dict) -> list[dict]:
    """Every live CPCB reading for the area, averaged across stations per
    timestamp and sorted oldest -> newest. Used for 24h-change, trend and
    spike detection when there isn't enough (or any) historical daily data."""
    f = area_record_filter(resolved)
    rows = list(M.col(M.AQI_RECORDS).find(dict(f, grain="live"), _PROJ).sort("ts", 1))
    rows = [r for r in rows if r.get("AQI") is not None]
    by_ts: dict[Any, list[dict]] = {}
    for r in rows:
        by_ts.setdefault(r["ts"], []).append(r)
    out = []
    for ts in sorted(by_ts):
        group = by_ts[ts]
        agg: dict[str, Any] = {"ts": ts, "date": ts.strftime("%Y-%m-%d")}
        for k in ["AQI"] + POLLUTANTS:
            vals = [g[k] for g in group if g.get(k) is not None]
            agg[k] = round(mean(vals), 2) if vals else None
        out.append(agg)
    return out


def _value_change(before: float | None, after: float | None) -> dict | None:
    if before is None or after is None:
        return None
    abs_change = round(after - before, 2)
    pct = round(100 * (after - before) / before, 1) if before else None
    return {"from": before, "to": after, "abs": abs_change, "pct": pct}


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


_HEALTH_RELEVANCE = {
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


def pollutants(state: str, area: str, trend_days: int = 30) -> dict:
    """Per-pollutant current value, 24h change, trend stats and health/source
    context. Falls back to the live CPCB series when there is no historical
    daily data for the area (true for most post-2020 LGD districts), instead
    of incorrectly reporting the area as having no data at all."""
    resolved = resolve_area(state, area)
    hist_series = _pick_series_docs(resolved)
    live_series = _area_live_series(resolved) if not hist_series else []

    series = hist_series or live_series
    if not series:
        return {"available": False, "reason": "No records for this area."}

    is_live = not hist_series
    latest = series[-1]
    cutoff = latest["ts"] - timedelta(days=trend_days)
    window = [d for d in series if d["ts"] >= cutoff]

    # 24h-change: nearest earlier point to ~24h before the latest reading,
    # in the same series that's actually available for this area.
    target = latest["ts"] - timedelta(hours=24)
    earlier = [d for d in series if d["ts"] <= target]
    prior = min(earlier, key=lambda d: abs((d["ts"] - target).total_seconds())) \
        if earlier else None

    out = []
    for p in POLLUTANTS:
        vals = [d[p] for d in window if d.get(p) is not None]
        live_published = p in LIVE_PUBLISHED_POLLUTANTS
        note = None
        if is_live and not live_published:
            note = ("Not published by the CPCB real-time feed for this area "
                     "right now; only available in historical (2015-2020) records.")
        out.append({
            "pollutant": p,
            "current": latest.get(p),
            "unit": "mg/m³" if p == "CO" else "µg/m³",
            "change_24h": _value_change(prior.get(p) if prior else None, latest.get(p)),
            "trend_mean": round(mean(vals), 2) if vals else None,
            "trend_min": round(min(vals), 2) if vals else None,
            "trend_max": round(max(vals), 2) if vals else None,
            "trend_days": trend_days if hist_series else None,
            "trend_source": "historical_daily" if hist_series else "live_readings",
            "n": len(vals),
            "health_relevance": _HEALTH_RELEVANCE.get(p, ""),
            "possible_source_categories": POLLUTANT_SOURCE_HINTS.get(p, []),
            "live_feed_note": note,
        })
    return {"available": True, "as_of": latest.get("date") or latest["ts"].isoformat(),
            "is_live": is_live,
            "state": state, "area": area, "trend_days": trend_days,
            "pollutants": out}
