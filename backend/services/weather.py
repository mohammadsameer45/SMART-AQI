"""
Open-Meteo weather layer for SMART AQI.

No API key. Current conditions + a 7-day daily outlook for a resolved area,
using the coordinates of a geolocated monitoring station in that area. If the
area has no station with coordinates, weather is reported unavailable rather
than guessed.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from backend.config import config
from backend.models import mongo_models as M
from backend.services.location_service import area_record_filter, resolve_area

_CURRENT = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
            "surface_pressure", "precipitation", "weather_code"]
_DAILY = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum",
          "wind_speed_10m_max", "weather_code"]

# condensed WMO weather-code groups
_WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 61: "Light rain", 63: "Rain", 65: "Heavy rain",
    66: "Freezing rain", 67: "Freezing rain", 71: "Light snow", 73: "Snow",
    75: "Heavy snow", 80: "Rain showers", 81: "Rain showers",
    82: "Violent rain showers", 95: "Thunderstorm", 96: "Thunderstorm",
    99: "Thunderstorm with hail",
}


def wmo_text(code) -> str:
    try:
        return _WMO.get(int(code), "—")
    except (TypeError, ValueError):
        return "—"


def _fetch(lat: float, lon: float) -> dict:
    qs = urllib.parse.urlencode({
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "current": ",".join(_CURRENT), "daily": ",".join(_DAILY),
        "forecast_days": 7, "timezone": "auto", "wind_speed_unit": "ms",
    })
    url = f"{config.OPEN_METEO_BASE}/v1/forecast?{qs}"
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.loads(r.read())
        except Exception as e:                       # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo request failed: {last}")


def _area_coord(resolved: dict) -> tuple[float, float, str] | None:
    """A representative (lat, lon, station-name) for the resolved area."""
    q = area_record_filter(resolved)
    for doc in M.col(M.LOCATIONS).find(
            {**q, "lat": {"$ne": None}, "lon": {"$ne": None}},
            {"lat": 1, "lon": 1, "station": 1, "city": 1}):
        return doc["lat"], doc["lon"], doc.get("station") or doc.get("city")
    # fall back to a live CPCB station in the same city
    for city in resolved.get("cities", []):
        d = M.col("cpcb_live").find_one(
            {"city": city, "lat": {"$ne": None}}, {"lat": 1, "lon": 1, "_id": 1})
        if d:
            return d["lat"], d["lon"], d["_id"]
    return None


def for_area(state: str, area: str) -> dict:
    resolved = resolve_area(state, area)
    coord = _area_coord(resolved)
    if not coord:
        return {"available": False,
                "reason": "No geolocated monitoring station in this area, so "
                          "weather cannot be shown without guessing a location."}
    lat, lon, at = coord
    try:
        raw = _fetch(lat, lon)
    except RuntimeError as e:
        return {"available": False, "reason": str(e)}

    cur = raw.get("current", {})
    daily = raw.get("daily", {})
    days = []
    for i, d in enumerate(daily.get("time", [])):
        days.append({
            "date": d,
            "t_max": daily["temperature_2m_max"][i],
            "t_min": daily["temperature_2m_min"][i],
            "rain_mm": daily["precipitation_sum"][i],
            "wind_max_ms": daily["wind_speed_10m_max"][i],
            "condition": wmo_text(daily["weather_code"][i]),
        })
    return {
        "available": True,
        "source": "Open-Meteo",
        "as_of": cur.get("time"),
        "location": {"lat": round(lat, 4), "lon": round(lon, 4),
                     "reference_station": at},
        "current": {
            "temperature": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind_speed": cur.get("wind_speed_10m"),
            "pressure": cur.get("surface_pressure"),
            "rainfall": cur.get("precipitation"),
            "condition": wmo_text(cur.get("weather_code")),
        },
        "units": {"temperature": "°C", "humidity": "%", "wind_speed": "m/s",
                  "pressure": "hPa", "rainfall": "mm"},
        "daily": days,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
