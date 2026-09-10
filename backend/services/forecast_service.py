"""7-day forecast retrieval for a resolved area (reads `forecast_records`)."""
from __future__ import annotations

from statistics import mean

from backend.config.aqi_categories import categorize
from backend.models import mongo_models as M
from backend.services.location_service import area_record_filter, resolve_area


def forecast(state: str, area: str, model: str | None = None) -> dict:
    resolved = resolve_area(state, area)
    f = area_record_filter(resolved)
    if model:
        f["model"] = model

    latest_run = M.col(M.FORECAST_RECORDS).find_one(f, sort=[("generated_at", -1)])
    if not latest_run:
        return {
            "forecast_available": False,
            "state": state, "area": area,
            "reason": "No 7-day forecast for this area yet. Forecasts are "
                      "generated only for stations with enough recent daily "
                      "history; broader coverage arrives with the live data "
                      "feed.",
        }

    f["generated_at"] = latest_run["generated_at"]
    f["model"] = latest_run["model"]
    rows = list(M.col(M.FORECAST_RECORDS).find(f, {"_id": 0}).sort("horizon_day", 1))

    # collapse multiple stations in the area to a per-horizon mean
    by_h: dict[int, list[dict]] = {}
    for r in rows:
        by_h.setdefault(r["horizon_day"], []).append(r)
    days = []
    for h in sorted(by_h):
        grp = by_h[h]
        val = round(mean(r["predicted_AQI"] for r in grp), 1)
        lo = round(mean(r["lower"] for r in grp), 1)
        hi = round(mean(r["upper"] for r in grp), 1)
        days.append({
            "horizon_day": h,
            "forecast_date": grp[0]["forecast_date"],
            "predicted_AQI": val,
            "AQI_display": min(val, 500),
            "AQI_bucket": categorize(val),
            "lower": lo, "upper": hi,
            "n_stations": len(grp),
        })
    return {
        "forecast_available": True,
        "state": state, "area": area,
        "matched_level": resolved["matched_level"],
        "model": latest_run["model"],
        "generated_at": latest_run["generated_at"],
        "is_prediction": True,
        "method": rows[0].get("method") if rows else None,
        "note": "Predictions, not measurements. Uncertainty band widens with "
                "horizon.",
        "days": days,
    }
