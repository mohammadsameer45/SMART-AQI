"""
Health Advisory Engine (baseline).

Combines the current AQI category with the near-term forecast to assemble the
advisory cards. Informational decision-support only - never a diagnosis, never a
medication instruction. Content comes from `health_advisories` (seeded from CPCB
category health-impact statements + standard precautionary guidance).
"""
from __future__ import annotations

from backend.config.aqi_categories import AQI_CATEGORIES, categorize
from backend.models import mongo_models as M
from backend.services import aqi_service, forecast_service

_SEVERITY = {c["label"]: i for i, c in enumerate(AQI_CATEGORIES)}
AUDIENCES = ["general", "sensitive"]


def _advisory(bucket: str, audience: str) -> dict | None:
    return M.col(M.HEALTH_ADVISORIES).find_one(
        {"_id": f"{bucket}:{audience}"}, {"_id": 0})


def advisory(state: str, area: str) -> dict:
    cur = aqi_service.current(state, area)
    if not cur.get("available"):
        return {"available": False, "reason": cur.get("reason")}

    bucket = cur["AQI_bucket"] or categorize(cur["AQI"])
    cards = {a: _advisory(bucket, a) for a in AUDIENCES}

    # tomorrow / 7-day outlook from the forecast, if we have one
    fc = forecast_service.forecast(state, area)
    tomorrow = week = None
    if fc.get("forecast_available") and fc["days"]:
        d1 = fc["days"][0]
        tomorrow = {
            "forecast_date": d1["forecast_date"],
            "predicted_AQI": d1["predicted_AQI"],
            "AQI_bucket": d1["AQI_bucket"],
            "direction": _direction(cur["AQI"], d1["predicted_AQI"]),
            "advisory": _advisory(d1["AQI_bucket"], "sensitive"),
        }
        worst = max(fc["days"], key=lambda d: d["predicted_AQI"])
        week = {
            "worst_day": worst["forecast_date"],
            "worst_AQI": worst["predicted_AQI"],
            "worst_bucket": worst["AQI_bucket"],
            "buckets": [d["AQI_bucket"] for d in fc["days"]],
        }

    return {
        "available": True,
        "state": state, "area": area,
        "as_of": cur["as_of"],
        "current_AQI": cur["AQI"],
        "current_bucket": bucket,
        "severity": _SEVERITY.get(bucket, 0),
        "air_quality_status": cards["general"]["headline"] if cards["general"]
        else None,
        "who_should_take_care": _who(bucket),
        "outdoor_activity": (cards["general"] or {}).get("outdoor_activity"),
        "respiratory_precautions": (cards["sensitive"] or {}).get("guidance", []),
        "cards": cards,
        "tomorrow_risk": tomorrow,
        "seven_day_outlook": week,
        "disclaimer": (cards["general"] or {}).get("disclaimer"),
    }


def _who(bucket: str) -> list[str]:
    sev = _SEVERITY.get(bucket, 0)
    if sev <= 0:
        return []
    base = ["People with asthma or other respiratory conditions",
            "People with heart disease", "Children", "Older adults",
            "Pregnant people"]
    if sev >= 3:
        base += ["Outdoor workers", "People exercising outdoors"]
    return base


def _direction(today: float | None, tomorrow: float | None) -> str:
    if today is None or tomorrow is None:
        return "unknown"
    diff = tomorrow - today
    if abs(diff) < 10:
        return "steady"
    return "worsening" if diff > 0 else "improving"
