"""
Slim GeoJSON for the 3D India map, with the latest AQI attached per region.

geoBoundaries ADM1/ADM2 polygons are simplified and coordinate-rounded so the
payload is a few hundred KB, then each feature is tagged with the current AQI
for that state / district (live CPCB mean where available, else the latest
historical station mean). Built once and cached.
"""
from __future__ import annotations

import json
import time
import unicodedata
from functools import lru_cache
from statistics import mean

from shapely.geometry import mapping, shape

from backend.config import config
from backend.config.aqi_categories import categorize, category_meta
from backend.models import mongo_models as M

META = config.METADATA_DIR
ADM1 = META / "geoBoundaries-IND-ADM1_simplified.geojson"
ADM2 = META / "geoBoundaries-IND-ADM2_simplified.geojson"


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).strip()


def _round(o, nd=3):
    if isinstance(o, list):
        return [_round(x, nd) for x in o]
    if isinstance(o, float):
        return round(o, nd)
    return o


def _slim(features, name_key, tol):
    out = []
    for f in features:
        try:
            g = shape(f["geometry"]).simplify(tol, preserve_topology=True)
            if g.is_empty:
                continue
            out.append({
                "type": "Feature",
                "properties": {"name": (f["properties"].get(name_key) or "").strip()},
                "geometry": {"type": mapping(g)["type"],
                             "coordinates": _round(mapping(g)["coordinates"])},
            })
        except Exception:                            # noqa: BLE001
            continue
    return out


# ------------------------------------------------------------ AQI per region --
def _latest_state_aqi() -> dict[str, dict]:
    """state -> {aqi, bucket, n_stations, source}."""
    out: dict[str, dict] = {}
    # live first
    for row in M.col("cpcb_live").aggregate([
        {"$match": {"AQI": {"$ne": None}}},
        {"$group": {"_id": "$state", "aqi": {"$avg": "$AQI"},
                    "n": {"$sum": 1}}},
    ]):
        if row["_id"]:
            out[row["_id"]] = {"aqi": round(row["aqi"]), "n_stations": row["n"],
                               "source": "live"}
    # fill gaps from the latest historical station rows
    have = set(out)
    for st in M.col(M.AQI_RECORDS).distinct("state"):
        if st in have or not st:
            continue
        rows = list(M.col(M.AQI_RECORDS).find(
            {"state": st, "level": "station", "grain": "day",
             "AQI": {"$ne": None}},
            {"_id": 0, "AQI": 1, "date": 1}).sort("date", -1).limit(60))
        if rows:
            latest = rows[0]["date"]
            vals = [r["AQI"] for r in rows if r["date"] == latest]
            out[st] = {"aqi": round(mean(vals)), "n_stations": len(vals),
                       "source": "historical"}
    for st, d in out.items():
        d["bucket"] = categorize(d["aqi"])
    return out


def _latest_district_aqi(state: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in M.col(M.AQI_RECORDS).aggregate([
        {"$match": {"state": state, "district": {"$ne": None},
                    "AQI": {"$ne": None}}},
        {"$sort": {"ts": -1}},
        {"$group": {"_id": {"d": "$district", "day": "$date"},
                    "aqi": {"$avg": "$AQI"}, "ts": {"$first": "$ts"}}},
        {"$sort": {"ts": -1}},
        {"$group": {"_id": "$_id.d", "aqi": {"$first": "$aqi"}}},
    ]):
        if row["_id"]:
            out[row["_id"]] = {"aqi": round(row["aqi"]),
                               "bucket": categorize(round(row["aqi"]))}
    return out


# ------------------------------------------------------------------ builders --
@lru_cache(maxsize=1)
def _india_base() -> tuple:
    gj = json.loads(ADM1.read_text(encoding="utf-8"))
    return tuple(json.dumps(f) for f in _slim(gj["features"], "shapeName", 0.03))


_TTL = 300
_cache: dict[str, tuple[float, dict]] = {}


def _cached(key: str, build):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    val = build()
    _cache[key] = (time.time(), val)
    return val


def india() -> dict:
    return _cached("india", _india)


def _india() -> dict:
    feats = [json.loads(s) for s in _india_base()]
    aqi = _latest_state_aqi()
    # our dataset state names vs geoBoundaries' (diacritics / spelling)
    norm = {_deaccent(k).lower(): k for k in aqi}
    for f in feats:
        key = norm.get(_deaccent(f["properties"]["name"]).lower())
        d = aqi.get(key) if key else None
        f["properties"].update({
            "aqi": d["aqi"] if d else None,
            "aqi_bucket": d["bucket"] if d else None,
            "n_stations": d["n_stations"] if d else 0,
            "has_data": bool(d),
            "source": d["source"] if d else None,
            "dataset_state": key,
        })
    return {"type": "FeatureCollection", "level": "state", "features": feats}


@lru_cache(maxsize=16)
def _state_base(state: str) -> tuple:
    """ADM2 features for the districts that actually have data in `state`."""
    want = {d for d in M.col(M.LOCATIONS).distinct("district", {"state": state}) if d}
    if not want:
        return tuple()
    gj = json.loads(ADM2.read_text(encoding="utf-8"))
    keep = [f for f in gj["features"]
            if (f["properties"].get("shapeName") or "").strip() in want]
    return tuple(json.dumps(f) for f in _slim(keep, "shapeName", 0.015))


def state(name: str) -> dict:
    return _cached(f"state:{name}", lambda: _state(name))


def _state(name: str) -> dict:
    feats = [json.loads(s) for s in _state_base(name)]
    aqi = _latest_district_aqi(name)
    for f in feats:
        d = aqi.get(f["properties"]["name"])
        f["properties"].update({
            "aqi": d["aqi"] if d else None,
            "aqi_bucket": d["bucket"] if d else None,
            "has_data": bool(d),
        })
    return {"type": "FeatureCollection", "level": "district",
            "state": name, "features": feats}
