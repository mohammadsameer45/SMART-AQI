"""
24-hour forecast, outdoor-walk planner and pollution-recovery estimate for
SMART AQI - all built on top of the existing trained-model 7-day forecast
(forecast_service) and, where that model has no coverage for an area yet,
the real live CPCB series. Nothing here is a random or invented value.

24-hour method
---------------
There is no trained hourly model (the ML pipeline is daily-resolution only -
see backend/ml/forecast.py). Rather than fabricate an independent hourly
prediction, the 24h view takes the day-ahead (+1d) model forecast as the
near-term AQI level and distributes it across the next 24 hours using this
station's own real historical hour-of-day pattern (data/cleaned/
station_hour.csv.gz, the 2015-2020 CPCB hourly dataset already in the
project) - i.e. a real, measured diurnal shape, scaled to a real model
forecast. This is explicitly labelled as an estimate, not an independent
per-hour ML prediction.

For an area with no trained-model forecast at all (most of the districts
Phase 1 newly mapped - the models were trained only on the ~94 historical
stations), a much shorter (~6h) linear projection of the recent *live*
reading trend is offered instead, clearly labelled as lower-confidence. If
neither is available, the function says so.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from statistics import mean

import numpy as np
import pandas as pd

from backend.config.aqi_categories import categorize
from backend.services import aqi_service, forecast_service
from backend.services.location_service import resolve_area

ROOT = Path(__file__).resolve().parents[2]
STATION_HOUR = ROOT / "data" / "cleaned" / "station_hour.csv.gz"
_MIN_HOURLY_POINTS = 24 * 7          # ~1 week of real hourly points for a stable shape


@lru_cache(maxsize=1)
def _station_hourly() -> pd.DataFrame | None:
    if not STATION_HOUR.exists():
        return None
    df = pd.read_csv(STATION_HOUR, usecols=["station_id", "date", "AQI"])
    df = df.dropna(subset=["AQI"])
    df["hour"] = df["date"].str.slice(11, 13).astype(int)
    return df


def _diurnal_shape(station_ids: list[str]) -> dict[int, float] | None:
    """hour(0-23) -> multiplier of that station set's own overall mean AQI,
    from real 2015-2020 hourly CPCB readings. None if no usable history."""
    df = _station_hourly()
    if df is None or not station_ids:
        return None
    sub = df[df["station_id"].isin(station_ids)]
    if len(sub) < _MIN_HOURLY_POINTS:
        return None
    overall = sub["AQI"].mean()
    if not overall:
        return None
    by_hour = sub.groupby("hour")["AQI"].mean()
    return {int(h): round(float(v) / overall, 4) for h, v in by_hour.items()}


def forecast_24h(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)
    fc = forecast_service.forecast(state, area)
    now = datetime.now(timezone.utc)

    if fc.get("forecast_available"):
        day1 = fc["days"][0]
        shape = _diurnal_shape(resolved.get("stations", []))
        hours = []
        for i in range(24):
            t = now + timedelta(hours=i + 1)
            mult = shape.get(t.hour, 1.0) if shape else 1.0
            val = round(day1["predicted_AQI"] * mult, 1)
            hours.append({
                "time": t.strftime("%Y-%m-%dT%H:00"),
                "hour_label": t.strftime("%H:00"),
                "predicted_AQI": max(val, 0),
                "AQI_bucket": categorize(val),
                "lower": round(day1["lower"] * mult, 1) if shape else day1["lower"],
                "upper": round(day1["upper"] * mult, 1) if shape else day1["upper"],
            })
        method = "model_diurnal" if shape else "flat_day1"
        note = ("Hourly shape estimated from this area's own real historical "
                "(2015-2020) hour-of-day AQI pattern, scaled to match the "
                "day-ahead model forecast. Not an independent hour-by-hour "
                "ML prediction." if shape else
                "No historical hourly pattern available for this area's "
                "station(s); showing the day-ahead forecast value applied "
                "uniformly across the next 24 hours.")
        return {"available": True, "state": state, "area": area, "method": method,
                "model": fc.get("model"), "generated_at": fc.get("generated_at"),
                "hours": hours, "note": note}

    live_series = aqi_service._area_live_series(resolved)
    pts = [(d["ts"], d["AQI"]) for d in live_series if d.get("AQI") is not None]
    if len(pts) >= 5:
        base_t = pts[-1][0]
        recent = pts[-8:]
        xs = np.array([(t - base_t).total_seconds() / 3600 for t, _ in recent])
        ys = np.array([v for _, v in recent])
        slope, intercept = (np.polyfit(xs, ys, 1) if np.ptp(xs) > 0 else (0.0, ys[-1]))
        hours = []
        for i in range(6):
            t = now + timedelta(hours=i + 1)
            dt_h = (t - base_t).total_seconds() / 3600
            val = max(round(float(intercept + slope * dt_h), 1), 0)
            hours.append({"time": t.strftime("%Y-%m-%dT%H:00"),
                          "hour_label": t.strftime("%H:00"),
                          "predicted_AQI": val, "AQI_bucket": categorize(val),
                          "lower": None, "upper": None})
        return {"available": True, "state": state, "area": area,
                "method": "live_trend_projection", "hours": hours,
                "note": "Short-term (~6h) linear projection from the recent "
                        "live-reading trend - this area doesn't yet have "
                        "enough historical depth for the trained daily "
                        "model, so this is a lower-confidence estimate, not "
                        "a full 24-hour forecast."}

    return {"available": False,
            "reason": "Not enough historical or live data yet for an hourly "
                      "forecast in this area."}


def outdoor_planner(state: str, area: str, window_hours: int = 3) -> dict:
    h24 = forecast_24h(state, area)
    if not h24.get("available"):
        return {"available": False, "reason": h24.get("reason")}
    hours = h24["hours"]
    if len(hours) < window_hours:
        return {"available": False, "reason": "Not enough forecast hours for a window."}

    scored = []
    for i in range(len(hours) - window_hours + 1):
        chunk = hours[i:i + window_hours]
        scored.append((mean(c["predicted_AQI"] for c in chunk), chunk))
    best_avg, best_chunk = min(scored, key=lambda x: x[0])
    worst_avg, worst_chunk = max(scored, key=lambda x: x[0])

    def _summ(avg, chunk):
        vals = [c["predicted_AQI"] for c in chunk]
        return {"start": chunk[0]["hour_label"], "end": chunk[-1]["hour_label"],
                "avg_AQI": round(avg, 1), "min_AQI": round(min(vals), 1),
                "max_AQI": round(max(vals), 1), "AQI_bucket": categorize(avg)}

    return {"available": True, "state": state, "area": area,
            "method": h24["method"],
            "best_window": _summ(best_avg, best_chunk),
            "avoid_window": _summ(worst_avg, worst_chunk),
            "note": "Based on the 24-hour AQI estimate above - guidance "
                    "only, not a health guarantee. Check current conditions "
                    "before heading out."}


def recovery_prediction(state: str, area: str) -> dict:
    cur = aqi_service.current(state, area)
    if not cur.get("available"):
        return {"available": False, "reason": cur.get("reason")}

    resolved = resolve_area(state, area)
    hist = aqi_service._pick_series_docs(resolved)
    series = hist if hist else aqi_service._area_live_series(resolved)
    recent = [d for d in series if d.get("AQI") is not None and
             d["ts"] >= series[-1]["ts"] - timedelta(days=3)] if series else []
    peak = round(max((d["AQI"] for d in recent), default=cur["AQI"]), 1)

    from backend.services.pollutant_insight_service import trend as trend_fn
    tr = trend_fn(state, area)
    declining = bool(tr.get("available") and tr["classification"] == "improved")

    fc = forecast_service.forecast(state, area)
    predicted_next = None
    recovery = None
    if fc.get("forecast_available") and fc["days"]:
        predicted_next = fc["days"][0]["predicted_AQI"]
        for d in fc["days"]:
            if d["predicted_AQI"] <= 100:          # CPCB "Satisfactory" or better
                recovery = {"forecast_date": d["forecast_date"],
                           "horizon_day": d["horizon_day"],
                           "predicted_AQI": d["predicted_AQI"],
                           "AQI_bucket": d["AQI_bucket"]}
                break

    return {
        "available": True, "state": state, "area": area,
        "current_AQI": cur["AQI"], "current_bucket": cur.get("AQI_bucket"),
        "peak_AQI_last_3d": peak,
        "is_declining": declining,
        "trend": {"classification": tr.get("classification"),
                 "percent_change": tr.get("percent_change")} if tr.get("available") else None,
        "predicted_next": predicted_next,
        "forecast_available": fc.get("forecast_available", False),
        "estimated_recovery": recovery,
        "note": ("Estimated recovery: the first forecast day the model "
                 "predicts AQI at or below 100 (CPCB 'Satisfactory' or "
                 "better). Not guaranteed - conditions can change."
                 if fc.get("forecast_available") else
                 "No trained-model forecast for this area yet, so a "
                 "recovery date can't be estimated - only the current "
                 "trend is shown."),
    }
