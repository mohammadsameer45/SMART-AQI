"""
Forest-fire detection and fire -> smoke -> impact analysis for SMART AQI.

Source: NASA FIRMS (Fire Information for Resource Management System),
VIIRS_SNPP_NRT near-real-time active-fire detections - a real satellite
data feed, not invented. Requires FIRMS_MAP_KEY (free, user-registered) in
backend/.env; never exposed to the frontend.

Fire -> smoke -> impact is a *geometric estimate*: real fire coordinates,
real distance (haversine) and bearing to the selected area, and real wind
direction/speed from Open-Meteo (via weather.for_area) - combined into a
Low/Moderate/High "potential impact" label. This is explicitly a simplified
dispersion model (straight-line downwind cone), not a smoke-transport
simulation, and is labelled as such everywhere it's surfaced. It never
claims a fire *caused* any specific AQI reading - "possible"/"estimated"
language throughout, matching the rest of this project's evidence
conventions.
"""
from __future__ import annotations

import csv
import io
import math

import requests

from backend.config import config
from backend.models import mongo_models as M
from backend.services.location_service import resolve_area
from backend.services.weather import _area_coord, for_area as weather_for_area

SOURCE = "VIIRS_SNPP_NRT"
_DEFAULT_RADIUS_KM = 200
_DEFAULT_DAY_RANGE = 2
_KM_PER_DEG_LAT = 111.0


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2)
    return 2 * r * math.asin(min(1, math.sqrt(a)))


def _bearing_deg(lat1, lon1, lat2, lon2) -> float:
    """Initial compass bearing (0=N, 90=E, ...) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def _fetch_fires_raw(lat: float, lon: float, radius_km: int, day_range: int) -> list[dict]:
    if not config.FIRMS_MAP_KEY:
        raise RuntimeError("FIRMS_MAP_KEY not set in backend/.env")
    dlat = radius_km / _KM_PER_DEG_LAT
    dlon = radius_km / (_KM_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.1))
    bbox = f"{lon - dlon:.4f},{lat - dlat:.4f},{lon + dlon:.4f},{lat + dlat:.4f}"
    url = f"{config.FIRMS_BASE}/{config.FIRMS_MAP_KEY}/{SOURCE}/{bbox}/{day_range}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text or text.lower().startswith("invalid"):
        return []
    return list(csv.DictReader(io.StringIO(text)))


def detect_fires(state: str, area: str, radius_km: int = _DEFAULT_RADIUS_KM,
                 day_range: int = _DEFAULT_DAY_RANGE) -> dict:
    resolved = resolve_area(state, area)
    coord = _area_coord(resolved)
    if not coord:
        return {"available": False,
                "reason": "No geolocated monitoring station in this area, so "
                          "distance to a fire can't be computed."}
    lat, lon, at = coord

    try:
        rows = _fetch_fires_raw(lat, lon, radius_km, day_range)
    except Exception as e:                            # noqa: BLE001
        return {"available": False, "reason": f"FIRMS request failed: {e}"}

    fires = []
    for r in rows:
        try:
            flat, flon = float(r["latitude"]), float(r["longitude"])
        except (KeyError, ValueError):
            continue
        dist = round(_haversine_km(lat, lon, flat, flon), 1)
        if dist > radius_km:
            continue
        fires.append({
            "lat": flat, "lon": flon,
            "distance_km": dist,
            "bearing_from_fire_to_area_deg": round(_bearing_deg(flat, flon, lat, lon), 1),
            "acquired_date": r.get("acq_date"),
            "acquired_time_utc": r.get("acq_time"),
            "satellite": r.get("satellite"),
            "instrument": r.get("instrument"),
            "confidence": r.get("confidence"),
            "frp_mw": _num(r.get("frp")),
            "daynight": r.get("daynight"),
        })
    fires.sort(key=lambda f: f["distance_km"])

    return {
        "available": True,
        "state": state, "area": area,
        "reference_point": {"lat": lat, "lon": lon, "near": at},
        "source": f"NASA FIRMS ({SOURCE})",
        "radius_km": radius_km, "day_range": day_range,
        "count": len(fires),
        "fires": fires[:20],
        "message": (f"{len(fires)} active fire detection(s) within {radius_km} km."
                    if fires else
                    "No active fire detected from the configured fire-monitoring source."),
    }


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _nearby_station_names(flat: float, flon: float, wind_toward_deg: float,
                          max_km: float = 250, cone_deg: float = 45) -> list[dict]:
    """Real live CPCB stations that fall within the downwind cone from a fire,
    by their own recorded coordinates - not an invented list of places."""
    out = []
    for d in M.col("cpcb_live").find({"lat": {"$ne": None}, "lon": {"$ne": None}},
                                     {"city": 1, "lat": 1, "lon": 1, "_id": 0}):
        dist = _haversine_km(flat, flon, d["lat"], d["lon"])
        if dist < 1 or dist > max_km:
            continue
        bearing = _bearing_deg(flat, flon, d["lat"], d["lon"])
        if _angular_diff(bearing, wind_toward_deg) <= cone_deg:
            out.append({"city": d.get("city"), "distance_km": round(dist, 1)})
    seen, uniq = set(), []
    for c in sorted(out, key=lambda x: x["distance_km"]):
        if c["city"] not in seen:
            seen.add(c["city"])
            uniq.append(c)
    return uniq[:8]


def fire_impact(state: str, area: str, radius_km: int = _DEFAULT_RADIUS_KM) -> dict:
    det = detect_fires(state, area, radius_km)
    if not det.get("available"):
        return det
    if det["count"] == 0:
        return {"available": True, "state": state, "area": area,
                "fire_detected": False, "message": det["message"],
                "show_warning": False}

    fire = det["fires"][0]
    wx = weather_for_area(state, area)
    wind = None
    impact_level = "Unknown"
    alignment = None
    affected = []

    if wx.get("available") and wx["current"].get("wind_direction_deg") is not None:
        wind_from = wx["current"]["wind_direction_deg"]
        wind_toward = (wind_from + 180) % 360
        diff = _angular_diff(fire["bearing_from_fire_to_area_deg"], wind_toward)
        alignment = ("downwind" if diff <= 45 else
                     "partially downwind" if diff <= 90 else "not downwind")
        if alignment == "not downwind":
            impact_level = "Low"
        elif fire["distance_km"] < 50:
            impact_level = "High"
        elif fire["distance_km"] < 150:
            impact_level = "Moderate"
        else:
            impact_level = "Low"
        wind = {"speed_ms": wx["current"]["wind_speed"],
               "speed_kmh": round(wx["current"]["wind_speed"] * 3.6, 1)
               if wx["current"]["wind_speed"] is not None else None,
               "direction": wx["current"]["wind_direction"],
               "direction_deg": wind_from, "blowing_toward_deg": round(wind_toward, 1)}
        if alignment != "not downwind":
            affected = _nearby_station_names(fire["lat"], fire["lon"], wind_toward)

    return {
        "available": True, "state": state, "area": area,
        "fire_detected": True,
        "nearest_fire": fire,
        "distance_km": fire["distance_km"],
        "wind": wind,
        "alignment": alignment,
        "potential_impact_level": impact_level,
        "potentially_affected": affected,
        "show_warning": impact_level in ("Moderate", "High"),
        "label": "Estimated smoke impact zone",
        "note": ("Simplified straight-line dispersion estimate from the "
                 "fire's real location, real distance, and current wind "
                 "direction - not a smoke-transport simulation, and not "
                 "proof this fire is affecting AQI here. Treat "
                 "'potential impact' as a possibility to watch, not a "
                 "confirmed effect."),
    }
