"""
Geographic resolution for SMART AQI.

The dataset's leaf is currently the monitoring *city* (district is null until the
station -> ADM2 spatial join runs). To keep the API stable now and after that
join, an "area" path segment is matched against `district` first, then `city`.
`/states/:state/districts` reports which level it actually returned.
"""
from __future__ import annotations

from typing import Any

from backend.models import mongo_models as M
from backend.utils.responses import ApiError


def list_states() -> list[str]:
    return M.list_states()


def areas_for_state(state: str) -> dict[str, Any]:
    """Districts if any exist for the state, otherwise cities. `level` says which."""
    if not M.col(M.LOCATIONS).find_one({"state": state}):
        raise ApiError("unknown_state", f"No data for state '{state}'", 404)
    districts = sorted(d for d in M.col(M.LOCATIONS).distinct(
        "district", {"state": state}) if d)
    if districts:
        return {"level": "district", "items": districts}
    cities = sorted(c for c in M.col(M.LOCATIONS).distinct(
        "city", {"state": state}) if c)
    return {"level": "city", "items": cities}


def resolve_area(state: str, area: str) -> dict[str, Any]:
    """-> {state, area, matched_level, city_docs, stations[], cities[]}."""
    q = {"state": state, "$or": [{"district": area}, {"city": area}]}
    docs = list(M.col(M.LOCATIONS).find(q, {"_id": 0}))
    if not docs:
        raise ApiError("unknown_area",
                       f"No data for '{area}' in '{state}'", 404)
    matched_level = "district" if any(d.get("district") == area for d in docs) \
        else "city"
    stations = sorted({d["station_id"] for d in docs
                       if d.get("station_id")})
    cities = sorted({d["city"] for d in docs if d.get("city")})
    return {"state": state, "area": area, "matched_level": matched_level,
            "location_docs": docs, "stations": stations, "cities": cities}


def area_record_filter(resolved: dict) -> dict:
    """Mongo filter selecting aqi_records / forecast_records for a resolved area."""
    ors: list[dict] = []
    if resolved["stations"]:
        ors.append({"station_id": {"$in": resolved["stations"]}})
    if resolved["cities"]:
        ors.append({"city": {"$in": resolved["cities"]}})
    f: dict = {"state": resolved["state"]}
    if ors:
        f["$or"] = ors
    return f


def coverage(resolved: dict) -> dict:
    docs = resolved["location_docs"]
    starts = [d["history_start"] for d in docs if d.get("history_start")]
    ends = [d["history_end"] for d in docs if d.get("history_end")]
    return {
        "matched_level": resolved["matched_level"],
        "n_stations": len(resolved["stations"]),
        "n_cities": len(resolved["cities"]),
        "history_start": min(starts) if starts else None,
        "history_end": max(ends) if ends else None,
        "total_records": sum(int(d.get("n_records", 0)) for d in docs),
    }
