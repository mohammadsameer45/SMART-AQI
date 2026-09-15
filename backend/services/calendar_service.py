"""
AQI heat calendar for SMART AQI - day-by-day historical AQI intensity for an
area (GitHub-contribution-calendar style), built entirely from the real
2015-2020 Kaggle-sourced daily series already in aqi_records. Each day is
also joined against the real historical weather backfill
(data/processed/weather_history.parquet, itself real Open-Meteo archive
data for this project's stations) and given a "main pollutant" from the
CPCB sub-index breakpoints - no value here is estimated or invented.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from backend.config.aqi_breakpoints import compute_aqi
from backend.config.aqi_categories import categorize
from backend.services.aqi_service import POLLUTANTS, _pick_series_docs
from backend.services.location_service import resolve_area

ROOT = Path(__file__).resolve().parents[2]
WEATHER_HISTORY = ROOT / "data" / "processed" / "weather_history.parquet"


@lru_cache(maxsize=1)
def _weather_history() -> pd.DataFrame | None:
    if not WEATHER_HISTORY.exists():
        return None
    return pd.read_parquet(WEATHER_HISTORY)


def _weather_by_date(station_ids: list[str]) -> dict[str, dict]:
    df = _weather_history()
    if df is None or not station_ids:
        return {}
    sub = df[df["station_id"].isin(station_ids)]
    if sub.empty:
        return {}
    agg = sub.groupby("date").agg(
        temp_mean=("temp_mean", "mean"), humidity=("humidity", "mean"),
        wind_mean=("wind_mean", "mean"), rain=("rain", "mean")).reset_index()
    out = {}
    for _, r in agg.iterrows():
        out[str(r["date"])] = {
            "temp_mean": round(r["temp_mean"], 1) if pd.notna(r["temp_mean"]) else None,
            "humidity": round(r["humidity"], 1) if pd.notna(r["humidity"]) else None,
            "wind_mean_ms": round(r["wind_mean"], 1) if pd.notna(r["wind_mean"]) else None,
            "rain_mm": round(r["rain"], 1) if pd.notna(r["rain"]) else None,
        }
    return out


def calendar(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)
    series = _pick_series_docs(resolved)
    if not series:
        return {"available": False,
                "reason": "No historical (2015-2020) daily data for this area."}

    weather = _weather_by_date(resolved.get("stations", []))

    days = []
    for d in series:
        if d.get("AQI") is None:
            continue
        concentrations = {p: d.get(p) for p in POLLUTANTS}
        _, subs, _ = compute_aqi(concentrations)
        main_pollutant = max(subs, key=subs.get) if subs else None
        date = d["date"]
        days.append({
            "date": date,
            "AQI": d["AQI"],
            "AQI_bucket": d.get("AQI_bucket") or categorize(d["AQI"]),
            "main_pollutant": main_pollutant,
            "weather": weather.get(date),
        })

    monthly: dict[str, list[float]] = {}
    for d in days:
        monthly.setdefault(d["date"][:7], []).append(d["AQI"])
    monthly_avg = sorted(
        [{"month": m, "avg_AQI": round(sum(v) / len(v), 1), "n_days": len(v)}
         for m, v in monthly.items()], key=lambda x: x["month"])

    worst_days = sorted(days, key=lambda d: -d["AQI"])[:10]
    best_days = sorted(days, key=lambda d: d["AQI"])[:10]
    worst_month = max(monthly_avg, key=lambda m: m["avg_AQI"]) if monthly_avg else None
    best_month = min(monthly_avg, key=lambda m: m["avg_AQI"]) if monthly_avg else None

    return {
        "available": True, "state": state, "area": area,
        "n_days": len(days),
        "start": days[0]["date"] if days else None,
        "end": days[-1]["date"] if days else None,
        "days": days,
        "monthly": monthly_avg,
        "worst_days": worst_days, "best_days": best_days,
        "worst_month": worst_month, "best_month": best_month,
        "note": "Historical (2015-2020) daily AQI only - real recorded "
                "values, not live or predicted.",
    }
