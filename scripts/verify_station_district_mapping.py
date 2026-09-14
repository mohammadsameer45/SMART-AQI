"""Read-only audit: re-run the same point-in-polygon check
build_station_districts.py used, against data/metadata/station_district_map.json,
and report Matched / Mismatched / Outside. Writes nothing.

Uses the same current LGD_Districts.parquet boundary source as
build_station_districts.py (not the older geoBoundaries ADM2 file, which
predates the 2022+ district reorganisations and would report every correctly
re-assigned new district - e.g. Anakapalli, NTR - as a false "mismatch").
"""
import csv
import json
from pathlib import Path

import pandas as pd
from shapely import wkb
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
LGD_CSV = ROOT / "data" / "lgd_districts.csv"
LGD_PARQUET = ROOT / "data" / "metadata" / "LGD_Districts.parquet"
MAPPING_PATH = ROOT / "data" / "metadata" / "station_district_map.json"


def load_lgd_names():
    out = {}
    with open(LGD_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[(int(row["state_code"]), int(row["district_code"]))] = \
                row["district_name_english"].strip()
    return out


def load_boundaries():
    names = load_lgd_names()
    df = pd.read_parquet(LGD_PARQUET)
    boundaries = []
    for row in df.itertuples(index=False):
        key = (int(row.state_lgd), int(row.dist_lgd))
        district = names.get(key, row.dtname)
        boundaries.append({"district": district, "geometry": wkb.loads(row.geometry)})
    return boundaries


def find_district(lat, lon, boundaries):
    point = Point(float(lon), float(lat))
    matches = [
        b["district"]
        for b in boundaries
        if b["geometry"].contains(point) or b["geometry"].touches(point)
    ]
    return matches[0] if matches else None


def main():
    print("Loading current LGD district boundaries...")
    boundaries = load_boundaries()
    print(f"LGD district boundaries loaded: {len(boundaries)}")

    print("Loading existing station mapping...")
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    print(f"Stations in mapping: {len(mapping)}")
    print()

    matched = 0
    mismatched = 0
    outside = 0
    mismatches = []

    for key, station in mapping.items():
        lat = station.get("lat")
        lon = station.get("lon")
        if lat is None or lon is None:
            continue

        polygon_district = find_district(lat, lon, boundaries)
        existing_district = station.get("district")

        if polygon_district is None:
            outside += 1
            print(f"[OUTSIDE] {station.get('station')} ({lat}, {lon})")
        elif polygon_district == existing_district:
            matched += 1
        else:
            mismatched += 1
            mismatches.append({
                "station": station.get("station"),
                "station_id": station.get("station_id"),
                "existing": existing_district,
                "polygon": polygon_district,
                "lat": lat,
                "lon": lon,
            })

    print()
    print("=" * 70)
    print("STATION -> DISTRICT VERIFICATION (current LGD boundaries)")
    print("=" * 70)
    print(f"Matched:    {matched}")
    print(f"Mismatched: {mismatched}")
    print(f"Outside:    {outside}")

    if mismatches:
        print()
        print("MISMATCHES")
        print("-" * 70)
        for item in mismatches:
            print(f"{item['station_id']} | {item['station']} | "
                  f"Existing: {item['existing']} | Polygon: {item['polygon']}")

    print()
    print("Verification complete.")


if __name__ == "__main__":
    main()
