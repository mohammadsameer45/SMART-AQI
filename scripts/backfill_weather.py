"""
backfill_weather.py  -  historical daily weather for the geolocated stations.

Pulls 2015-01-01 .. 2020-07-01 daily weather from the Open-Meteo archive API
(ERA5 reanalysis, no key) for every `locations` station that has coordinates,
and writes data/processed/weather_history.parquet:

    station_id, date, temp_mean, temp_max, temp_min, humidity,
    wind_mean, wind_max, pressure, rain

The archive API is rate-limited, so this paces requests, honours Retry-After on
429, and is RESUMABLE: stations already in the output parquet are skipped, so
re-running finishes an interrupted backfill.

Run:  python scripts/backfill_weather.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import mongo_models as M  # noqa: E402

OUT = ROOT / "data" / "processed" / "weather_history.parquet"
START, END = "2015-01-01", "2020-07-01"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DAILY = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
         "relative_humidity_2m_mean", "wind_speed_10m_mean",
         "wind_speed_10m_max", "surface_pressure_mean", "precipitation_sum"]
REN = {
    "temperature_2m_mean": "temp_mean", "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min", "relative_humidity_2m_mean": "humidity",
    "wind_speed_10m_mean": "wind_mean", "wind_speed_10m_max": "wind_max",
    "surface_pressure_mean": "pressure", "precipitation_sum": "rain",
}
PACE = 2.5          # seconds between successful requests
MAX_RETRY = 6


def _fetch(lat: float, lon: float) -> pd.DataFrame:
    qs = urllib.parse.urlencode({
        "latitude": round(lat, 4), "longitude": round(lon, 4),
        "start_date": START, "end_date": END, "daily": ",".join(DAILY),
        "timezone": "auto", "wind_speed_unit": "ms"})
    url = f"{ARCHIVE}?{qs}"
    delay = 8
    for attempt in range(MAX_RETRY):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                d = json.loads(r.read())["daily"]
            df = pd.DataFrame({"date": d["time"], **{REN[k]: d[k] for k in DAILY}})
            return df
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", delay))
                print(f"      429 — waiting {wait}s", flush=True)
                time.sleep(wait)
                delay = min(delay * 2, 120)
            else:
                raise
        except Exception as e:                       # noqa: BLE001
            print(f"      {type(e).__name__}: {e} — retry in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError("exhausted retries")


def _cell(lat: float, lon: float) -> tuple[float, float]:
    # ERA5 reanalysis is a ~0.25 deg grid: stations in one cell share the value.
    return (round(lat * 4) / 4, round(lon * 4) / 4)


def main() -> None:
    stns = list(M.col(M.LOCATIONS).find(
        {"level": "station", "lat": {"$ne": None}, "lon": {"$ne": None}},
        {"_id": 0, "station_id": 1, "station": 1, "lat": 1, "lon": 1}))

    # group stations by ERA5 grid cell -> one fetch per unique cell
    cells: dict[tuple, list[dict]] = {}
    for s in stns:
        cells.setdefault(_cell(s["lat"], s["lon"]), []).append(s)

    done: set[str] = set()
    existing = pd.DataFrame()
    if OUT.exists():
        existing = pd.read_parquet(OUT)
        done = set(existing["station_id"].unique())
    todo_cells = {c: sts for c, sts in cells.items()
                  if any(s["station_id"] not in done for s in sts)}
    print(f"{len(stns)} stations in {len(cells)} ERA5 cells · "
          f"{len(done)} stations already done · {len(todo_cells)} cells to fetch "
          f"({START}..{END})", flush=True)

    frames = [existing] if not existing.empty else []
    for i, (cell, sts) in enumerate(todo_cells.items(), 1):
        try:
            df = _fetch(*cell)
        except RuntimeError as e:
            print(f"  [{i}/{len(todo_cells)}] cell {cell}: SKIP ({e})", flush=True)
            continue
        for s in sts:
            d2 = df.copy()
            d2.insert(0, "station_id", s["station_id"])
            frames.append(d2)
        print(f"  [{i}/{len(todo_cells)}] cell {cell} -> "
              f"{len(sts)} station(s), {len(df)} days", flush=True)
        if i % 3 == 0:
            _save(frames)
        time.sleep(PACE)

    if not frames:
        print("nothing fetched — archive API is rate-limiting; re-run later "
              "(progress is resumable).")
        return
    _save(frames)
    out = pd.read_parquet(OUT)
    print(f"\nwrote {OUT}  ({len(out):,} station-days, "
          f"{out['station_id'].nunique()} stations)", flush=True)
    print(out[list(REN.values())].describe().round(1).to_string())


def _save(frames: list[pd.DataFrame]) -> None:
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(["station_id", "date"])
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    for c in REN.values():
        out[c] = pd.to_numeric(out[c], errors="coerce")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)


if __name__ == "__main__":
    main()
