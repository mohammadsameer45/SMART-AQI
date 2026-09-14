"""
build_station_districts.py  -  assign a real district to every geolocated station.

Uses data/metadata/LGD_Districts.parquet: district polygons mapped to LGD
codes, sourced from the government LGD/Bharatmaps service via
github.com/ramSeraph/indian_admin_boundaries (CC0 1.0). The older
geoBoundaries ADM2 file predates the 2022+ district reorganisations (e.g.
Andhra Pradesh's 13 -> 26 split) and either has no polygon for a new district
at all, or would silently place a station in the wrong current district where
an old district name happens to coincide with a still-existing one (e.g. a
Vijayawada station falls inside the old "Krishna" polygon, but Vijayawada is
now in the separate "NTR" district) - so it is no longer used for this
assignment. It is left in place for other consumers (e.g. the map GeoJSON
routes) that draw boundary shapes rather than assign records to districts.

The resulting district name is always looked up by LGD code in
data/lgd_districts.csv (not read off the polygon file's own `dtname`, which
has a few spelling/short-form differences) so it exactly matches the district
list the API/UI already serve from that file.

Two station populations are placed:
  1. `locations` docs (level="station") that have lat/lon - the historical
     Kaggle-station set, placed as before and propagated by station_id.
  2. Every `cpcb_live` doc, directly, using its own coordinates - this covers
     every live CPCB station, including ones that never matched a historical
     station by name and so never got a `locations` doc at all. Propagated
     onto aqi_records (grain="live") by station name, since those docs may
     have no station_id.

Writes:
  data/metadata/station_district_map.json   (historical entries + live-only)
  locations.district / .adm1_state
  aqi_records.district, forecast_records.district      (by station_id)
  aqi_records.district (grain="live")                  (by station name)
  cpcb_live.district                                   (by own coordinates)

No AQI value, pollutant reading, timestamp or other field is touched - only
the `district` (and `adm1_state`, on `locations`) attribute is set/corrected.

Needs: shapely, pandas, data/metadata/LGD_Districts.parquet, data/lgd_districts.csv.
"""
from __future__ import annotations

import csv
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
from shapely import wkb  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from backend.models import mongo_models as M  # noqa: E402

META = ROOT / "data" / "metadata"
LGD_CSV = ROOT / "data" / "lgd_districts.csv"
LGD_PARQUET = META / "LGD_Districts.parquet"


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).strip()


def _norm(s: str) -> str:
    return " ".join((s or "").split()).strip().lower()


def _load_lgd_names() -> dict[tuple[int, int], tuple[str, str]]:
    """(state_code, district_code) -> (district_name_english, state_name_english),
    read from the same LGD extract the state/district dropdown already uses,
    so an assigned district always matches the UI's own list exactly."""
    out: dict[tuple[int, int], tuple[str, str]] = {}
    with open(LGD_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[(int(row["state_code"]), int(row["district_code"]))] = (
                row["district_name_english"].strip(), row["state_name_english"].strip())
    return out


def _load_layer():
    names = _load_lgd_names()
    df = pd.read_parquet(LGD_PARQUET)
    polys, meta = [], []
    unresolved_codes = 0
    for row in df.itertuples(index=False):
        geom = wkb.loads(row.geometry)
        key = (int(row.state_lgd), int(row.dist_lgd))
        if key in names:
            district, adm1_state = names[key]
        else:
            unresolved_codes += 1
            district, adm1_state = row.dtname, row.stname
        polys.append(geom)
        meta.append({"district": district, "adm1_state": adm1_state})
    if unresolved_codes:
        print(f"  ({unresolved_codes} polygons had no matching LGD code in "
              f"lgd_districts.csv - used the polygon file's own name instead)")
    return STRtree(polys), polys, meta


def _locate(tree, polys, meta, pt):
    for idx in tree.query(pt):
        if polys[idx].contains(pt) or polys[idx].touches(pt):
            return meta[idx]
    try:
        nidx = tree.nearest(pt)
        if polys[nidx].distance(pt) < 0.05:      # ~5 km, coastal/simplified edge
            return meta[nidx]
    except Exception:                             # noqa: BLE001
        pass
    return None


def _place(tree, polys, meta, lat, lon, dataset_state):
    """Returns (district_or_None, adm1_state_or_None, cross_state_bool)."""
    pt = Point(lon, lat)
    hit = _locate(tree, polys, meta, pt)
    if not hit:
        return None, None, False
    district, adm1_state = hit["district"], hit["adm1_state"]
    ds = _deaccent(dataset_state or "")
    if adm1_state and ds and _deaccent(adm1_state).lower() != ds.lower():
        # coordinate lands in a different state than the dataset says (a
        # border station + a coarse simplified polygon) - the dataset's own
        # state is authoritative, so leave district unset rather than guess.
        return None, adm1_state, True
    return district, adm1_state, False


def main() -> None:
    if not LGD_PARQUET.exists():
        print(f"missing {LGD_PARQUET} - download LGD_Districts.parquet from "
              "github.com/ramSeraph/indian_admin_boundaries (release tag "
              "'districts') into data/metadata/ first")
        return

    tree, polys, meta = _load_layer()
    print(f"loaded {len(polys)} current LGD district polygons")

    mapping: dict[str, dict] = {}
    placed = 0
    cross_state = 0

    # --- 1. historical stations already linked into `locations` ---
    locs = list(M.col(M.LOCATIONS).find(
        {"lat": {"$ne": None}, "lon": {"$ne": None}},
        {"_id": 1, "station": 1, "station_id": 1, "state": 1, "lat": 1, "lon": 1}))
    print(f"{len(locs)} geolocated `locations` docs to place")

    historical_names = {_norm(d["station"]) for d in locs if d.get("station")}

    for d in locs:
        district, adm1_state, cs = _place(tree, polys, meta, d["lat"], d["lon"], d["state"])
        if cs:
            print(f"  ! {d.get('station')}: coord in {adm1_state}, dataset says "
                  f"{d['state']} -> district left unset")
            cross_state += 1
        rec = {"station": d.get("station"), "station_id": d.get("station_id"),
               "dataset_state": d["state"], "adm1_state": adm1_state,
               "district": district, "lat": d["lat"], "lon": d["lon"],
               "source": "historical"}
        mapping[d["_id"]] = rec
        M.col(M.LOCATIONS).update_one({"_id": d["_id"]}, {"$set": {
            "district": district, "adm1_state": adm1_state}})
        if d.get("station_id"):
            M.col(M.AQI_RECORDS).update_many(
                {"station_id": d["station_id"]}, {"$set": {"district": district}})
            M.col(M.FORECAST_RECORDS).update_many(
                {"station_id": d["station_id"]}, {"$set": {"district": district}})
        if district:
            placed += 1

    # --- 2. every live CPCB station, by its own coordinates ---
    live = list(M.col("cpcb_live").find(
        {"lat": {"$ne": None}, "lon": {"$ne": None}},
        {"_id": 1, "state": 1, "lat": 1, "lon": 1}))
    print(f"{len(live)} `cpcb_live` docs to place")
    live_placed = 0
    live_only = 0
    for d in live:
        district, adm1_state, cs = _place(tree, polys, meta, d["lat"], d["lon"], d["state"])
        if cs:
            cross_state += 1
        M.col("cpcb_live").update_one({"_id": d["_id"]}, {"$set": {"district": district}})
        M.col(M.AQI_RECORDS).update_many(
            {"station": d["_id"], "grain": "live"}, {"$set": {"district": district}})
        if district:
            live_placed += 1
        if _norm(d["_id"]) not in historical_names:
            live_only += 1
            mapping[f"live:{d['_id']}"] = {
                "station": d["_id"], "station_id": None,
                "dataset_state": d["state"], "adm1_state": adm1_state,
                "district": district, "lat": d["lat"], "lon": d["lon"],
                "source": "cpcb_live_only"}

    (META / "station_district_map.json").write_text(
        json.dumps(mapping, indent=2), encoding="utf-8")

    n_districts = len({v["district"] for v in mapping.values() if v["district"]})
    print(f"\n  ({cross_state} left unset: coordinate fell in another state)")
    print(f"historical: placed {placed}/{len(locs)}")
    print(f"live feed:  placed {live_placed}/{len(live)}  "
          f"({live_only} stations exist only in the live feed, not in `locations`)")
    print(f"total distinct districts covered: {n_districts}")
    print(f"wrote {META / 'station_district_map.json'} ({len(mapping)} entries)")


if __name__ == "__main__":
    main()
