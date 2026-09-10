"""
build_station_districts.py  -  assign a real district to every geolocated station.

For each `locations` document that has coordinates (filled by
scripts/ingest_cpcb_live.py), do a point-in-polygon lookup against the
geoBoundaries India ADM2 (district) and ADM1 (state) layers. This is a
geometric fact about a real coordinate — not a guess or a crosswalk.

Writes:
  data/metadata/station_district_map.json
  locations.district / .adm1_state       (per station)
  aqi_records.district, forecast_records.district   (propagated by station_id)
  cpcb_live.district                     (matched by coordinates)

Needs: shapely, the two GeoJSON files already in data/metadata/.
"""
from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely.geometry import shape, Point  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from backend.models import mongo_models as M  # noqa: E402

META = ROOT / "data" / "metadata"


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s or "")
                   if not unicodedata.combining(c)).strip()


def _load_layer(path: Path):
    gj = json.loads(path.read_text(encoding="utf-8"))
    polys, names = [], []
    for f in gj["features"]:
        geom = shape(f["geometry"])
        polys.append(geom)
        names.append(f["properties"].get("shapeName", ""))
    return STRtree(polys), polys, names


def _locate(tree, polys, names, pt):
    for idx in tree.query(pt):
        if polys[idx].contains(pt) or polys[idx].touches(pt):
            return (names[idx] or "").strip()
    # nearest fallback (a coastal station may sit just outside a simplified poly)
    try:
        nidx = tree.nearest(pt)
        if polys[nidx].distance(pt) < 0.05:      # ~5 km
            return (names[nidx] or "").strip()
    except Exception:                            # noqa: BLE001
        pass
    return None


def main() -> None:
    adm2 = _load_layer(META / "geoBoundaries-IND-ADM2_simplified.geojson")
    adm1 = _load_layer(META / "geoBoundaries-IND-ADM1_simplified.geojson")
    print(f"loaded {len(adm2[1])} districts, {len(adm1[1])} states")

    locs = list(M.col(M.LOCATIONS).find(
        {"lat": {"$ne": None}, "lon": {"$ne": None}},
        {"_id": 1, "station": 1, "station_id": 1, "state": 1, "lat": 1, "lon": 1}))
    print(f"{len(locs)} geolocated locations to place")
    if not locs:
        print("no coordinates yet — run scripts/ingest_cpcb_live.py first")
        return

    mapping = {}
    placed = 0
    cross_state = 0
    for d in locs:
        pt = Point(d["lon"], d["lat"])
        district = _locate(*adm2, pt)
        adm1_state = _deaccent(_locate(*adm1, pt) or "")

        # Guard: if the coordinate falls in a DIFFERENT state than the dataset
        # says (a border station + a coarse simplified polygon), we can't place
        # it confidently -> leave the district null rather than assign a wrong
        # one. The dataset's state is authoritative.
        ds = _deaccent(d["state"] or "")
        if district and adm1_state and ds and adm1_state.lower() != ds.lower():
            print(f"  ! {d.get('station')}: coord in {adm1_state}, dataset "
                  f"says {d['state']} -> district left unset")
            district = None
            cross_state += 1

        rec = {"station": d.get("station"), "station_id": d.get("station_id"),
               "dataset_state": d["state"], "adm1_state": adm1_state or None,
               "district": district, "lat": d["lat"], "lon": d["lon"]}
        mapping[d["_id"]] = rec
        # write district (or clear a stale one) across the collections
        M.col(M.LOCATIONS).update_one({"_id": d["_id"]}, {"$set": {
            "district": district, "adm1_state": adm1_state or None}})
        if d.get("station_id"):
            M.col(M.AQI_RECORDS).update_many(
                {"station_id": d["station_id"]}, {"$set": {"district": district}})
            M.col(M.FORECAST_RECORDS).update_many(
                {"station_id": d["station_id"]}, {"$set": {"district": district}})
        M.col("cpcb_live").update_one(
            {"lat": d["lat"], "lon": d["lon"]}, {"$set": {"district": district}})
        if district:
            placed += 1

    (META / "station_district_map.json").write_text(
        json.dumps(mapping, indent=2), encoding="utf-8")

    print(f"  ({cross_state} left unset: coordinate fell in another state)")
    n_districts = len({v["district"] for v in mapping.values() if v["district"]})
    mismatch = sum(1 for v in mapping.values()
                   if v["adm1_state"] and v["dataset_state"]
                   and _deaccent(v["dataset_state"]).lower() != v["adm1_state"].lower())
    print(f"placed {placed}/{len(locs)} into {n_districts} distinct districts")
    print(f"dataset-state vs ADM1-state disagreements: {mismatch} "
          "(usually spelling / boundary-simplification, not real errors)")
    print(f"wrote {META / 'station_district_map.json'}")


if __name__ == "__main__":
    main()
