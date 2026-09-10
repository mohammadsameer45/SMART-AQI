"""
clean_data.py  -  Phase 4 cleaning for SMART AQI.

Reads the raw Kaggle CSVs in data/raw/ and writes canonical, validated,
de-duplicated tables to data/cleaned/ (gzip CSV), plus a cleaning report to
data/validation/. Applies the 10 rules in docs/dataset.md section 5.

Rules recap:
  1  standardise column names to the canonical schema
  2  standardise state names; trim/casefold city + station
  3  recover State for city_day / city_hour via stations.csv
  4  parse dates; drop unparseable or future-dated rows
  5  coerce pollutant columns to numeric (non-numeric -> null)
  6  drop rows where every measurement (12 pollutants + AQI) is null
  7  null out physically implausible values (recorded, not row-deleted)
  8  de-duplicate on the natural key
  9  keep source AQI_Bucket where valid, else derive from CPCB thresholds
 10  write data/cleaned/ + refreshed data/validation/ report

Nothing is fabricated: missing measurements stay null.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config.aqi_categories import categorize, AQI_CATEGORIES  # noqa: E402

RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "cleaned"
VALID = ROOT / "data" / "validation"
META = ROOT / "data" / "metadata"
for d in (CLEAN, VALID, META):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- schema ------
RENAME = {"PM2.5": "PM25", "AQI_Bucket": "AQI_bucket"}
POLLUTANTS = ["PM25", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3",
              "Benzene", "Toluene", "Xylene"]
MEASURE_COLS = POLLUTANTS + ["AQI"]

# Physical sensor-fault ceilings, ug/m3 except CO (mg/m3). Concentrations
# strictly above these are treated as instrument errors -> nulled and counted.
# AQI is deliberately NOT in this table: Indian stations legitimately report
# values above the 500 scale cap during severe episodes (e.g. Delhi winter
# smog), so raw AQI is kept as measured and only negatives are nulled. Values
# above 500 are recorded as "out of scale" in the report for transparency.
PLAUSIBLE_MAX = {
    "PM25": 1000, "PM10": 2000, "NO": 500, "NO2": 500, "NOx": 600, "NH3": 500,
    "CO": 50, "SO2": 500, "O3": 800, "Benzene": 500, "Toluene": 500,
    "Xylene": 500,
}
AQI_HARD_MAX = 1000   # above this AQI is a computation error -> nulled

STATE_ALIASES = {
    "orissa": "Odisha", "pondicherry": "Puducherry",
    "uttaranchal": "Uttarakhand", "chattisgarh": "Chhattisgarh",
    "delhi": "Delhi", "nct of delhi": "Delhi",
}


def norm_state(s: object) -> object:
    if not isinstance(s, str):
        return None
    t = " ".join(s.split()).strip()
    if not t:
        return None
    return STATE_ALIASES.get(t.lower(), t)


def norm_text(s: object) -> object:
    if not isinstance(s, str):
        return None
    t = " ".join(s.split()).strip()
    return t or None


# ---------------------------------------------------------------- helpers -----
def jsonable(x):
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        v = float(x)
        return None if v != v else v
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x


def load_station_map() -> tuple[pd.DataFrame, dict, dict]:
    st = pd.read_csv(RAW / "stations.csv")
    st.columns = [c.strip().lstrip("﻿") for c in st.columns]
    st["StationId"] = st["StationId"].map(norm_text)
    st["StationName"] = st["StationName"].map(norm_text)
    st["City"] = st["City"].map(norm_text)
    st["State"] = st["State"].map(norm_state)
    st["Status"] = st["Status"].map(norm_text)
    st = st.dropna(subset=["StationId"]).drop_duplicates("StationId")
    sid_map = st.set_index("StationId")[["StationName", "City", "State"]].to_dict("index")
    # city -> state (unambiguous only; log collisions)
    city_state = {}
    for city, grp in st.dropna(subset=["City", "State"]).groupby("City"):
        states = sorted(grp["State"].unique())
        city_state[city] = states[0]
        if len(states) > 1:
            print(f"  ! city '{city}' maps to multiple states {states}; using {states[0]}")
    return st, sid_map, city_state


def clean_measure_frame(name: str, df: pd.DataFrame, grain: str,
                        sid_map: dict, city_state: dict) -> tuple[pd.DataFrame, dict]:
    rep: dict = {"file": name, "grain": grain, "rows_in": int(len(df))}
    df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})

    date_col = "Datetime" if "Datetime" in df.columns else "Date"
    dt = pd.to_datetime(df[date_col], errors="coerce")
    n_unparse = int(dt.isna().sum() - df[date_col].isna().sum())
    n_future = int((dt > pd.Timestamp.now()).sum())
    df = df.loc[dt.notna() & (dt <= pd.Timestamp.now())].copy()
    dt = dt.loc[df.index]
    rep["dropped_unparseable_date"] = n_unparse
    rep["dropped_future_date"] = n_future

    # geo columns
    if "StationId" in df.columns:
        df["station_id"] = df["StationId"].map(norm_text)
        meta = df["station_id"].map(lambda s: sid_map.get(s, {}))
        df["station"] = meta.map(lambda m: m.get("StationName"))
        df["city"] = meta.map(lambda m: m.get("City"))
        df["state"] = meta.map(lambda m: norm_state(m.get("State")))
        rep["rows_station_not_in_master"] = int(df["state"].isna().sum())
    else:
        df["station_id"] = None
        df["station"] = None
        df["city"] = df["City"].map(norm_text)
        df["state"] = df["city"].map(lambda c: city_state.get(c))
        rep["rows_city_without_state"] = int(df["state"].isna().sum())

    # numeric coercion
    for c in POLLUTANTS + ["AQI"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            df[c] = np.nan

    # implausible concentrations -> null (counted)
    outliers = {}
    for c, hi in PLAUSIBLE_MAX.items():
        bad = (df[c] < 0) | (df[c] > hi)
        n = int(bad.sum())
        if n:
            df.loc[bad, c] = np.nan
            outliers[c] = n
    # Known Kaggle artifact: CO column mis-filled with the NO value for some
    # station-periods (exact float equality across >1k rows is not chance).
    # The CO reading there is not trustworthy -> null it (NO is kept).
    co_misfill = df["CO"].notna() & df["NO"].notna() & (df["CO"] == df["NO"])
    n_co = int(co_misfill.sum())
    if n_co:
        df.loc[co_misfill, "CO"] = np.nan
        outliers["CO_equals_NO_misfill"] = n_co

    # AQI: null negatives and gross computation errors only; keep >500 as real
    aqi_bad = (df["AQI"] < 0) | (df["AQI"] > AQI_HARD_MAX)
    if int(aqi_bad.sum()):
        outliers["AQI"] = int(aqi_bad.sum())
        df.loc[aqi_bad, "AQI"] = np.nan
    rep["values_nulled_implausible"] = outliers
    rep["aqi_above_scale_500_kept"] = int((df["AQI"] > 500).sum())

    # drop rows with no measurement at all
    all_null = df[MEASURE_COLS].isna().all(axis=1)
    rep["dropped_all_measures_null"] = int(all_null.sum())
    df = df.loc[~all_null].copy()

    # canonical datetime
    dt = pd.to_datetime(df[date_col])
    if grain == "day":
        df["date"] = dt.dt.strftime("%Y-%m-%d")
    else:
        df["date"] = dt.dt.strftime("%Y-%m-%dT%H:%M:%S")
    df["grain"] = grain

    # AQI bucket: keep valid source label, else derive
    valid_labels = {c["label"] for c in AQI_CATEGORIES}
    src_bucket = df["AQI_bucket"].map(norm_text) if "AQI_bucket" in df.columns else pd.Series(index=df.index, dtype=object)
    derived = df["AQI"].map(categorize)
    df["AQI_bucket"] = [
        s if (isinstance(s, str) and s in valid_labels) else d
        for s, d in zip(src_bucket, derived)
    ]

    df["source"] = name.replace(".csv", "")
    df["ingested_at"] = datetime.now().isoformat(timespec="seconds")

    # natural-key dedupe
    key = (["station_id"] if grain and "station" in name else ["city"]) + ["date"]
    key = [k for k in key if k in df.columns]
    if "station_id" in df.columns and df["station_id"].notna().any():
        key = ["station_id", "date"]
    else:
        key = ["city", "date"]
    before = len(df)
    df = df.drop_duplicates(subset=key, keep="first")
    rep["duplicates_removed"] = int(before - len(df))

    out_cols = (["state", "city", "district", "station", "station_id",
                 "date", "grain"] + POLLUTANTS + ["AQI", "AQI_bucket",
                 "source", "ingested_at"])
    df["district"] = None  # filled later by the spatial join
    df = df[out_cols]

    rep["rows_out"] = int(len(df))
    rep["distinct_states"] = int(df["state"].nunique())
    rep["distinct_cities"] = int(df["city"].nunique())
    rep["distinct_stations"] = int(df["station_id"].nunique())
    rep["date_min"] = str(df["date"].min())
    rep["date_max"] = str(df["date"].max())
    rep["missing_pct_after"] = {
        c: round(100 * df[c].isna().mean(), 2) for c in MEASURE_COLS
    }
    rep["records_per_state"] = (
        df.groupby("state").size().sort_values(ascending=False).to_dict()
    )
    return df, rep


def main() -> None:
    print("loading station master ...")
    stations, sid_map, city_state = load_station_map()
    stations.to_csv(CLEAN / "stations.csv", index=False)

    (META / "state_list.json").write_text(
        json.dumps(sorted({v for v in city_state.values()} |
                          {norm_state(m["State"]) for m in sid_map.values()
                           if m.get("State")}), indent=2),
        encoding="utf-8")

    specs = [
        ("city_day.csv", "day"),
        ("station_day.csv", "day"),
        ("city_hour.csv", "hour"),
        ("station_hour.csv", "hour"),
    ]
    report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
              "files": {}}
    for fname, grain in specs:
        print(f"cleaning {fname} ({grain}) ...")
        df = pd.read_csv(RAW / fname, low_memory=False)
        cleaned, rep = clean_measure_frame(fname, df, grain, sid_map, city_state)
        out = CLEAN / fname.replace(".csv", ".csv.gz")
        cleaned.to_csv(out, index=False, compression="gzip")
        rep["output"] = str(out.relative_to(ROOT))
        report["files"][fname] = rep
        print(f"  -> {rep['rows_in']:,} in / {rep['rows_out']:,} out  -> {out.name}")
        del df, cleaned

    (VALID / "cleaning_report.json").write_text(
        json.dumps(report, indent=2, default=jsonable), encoding="utf-8")

    # ---- markdown ----
    L = ["# SMART AQI - Cleaning Report\n",
         f"_Generated {report['generated_at']} by `scripts/clean_data.py`. "
         "Missing measurements are left null - never imputed or fabricated._\n"]
    for fname, r in report["files"].items():
        L.append(f"\n## `{fname}` -> `{Path(r['output']).name}` ({r['grain']})\n")
        L.append(f"- Rows: **{r['rows_in']:,} -> {r['rows_out']:,}**")
        L.append(f"- Date range: {r['date_min']} -> {r['date_max']}")
        L.append(f"- Distinct: {r['distinct_states']} states, "
                 f"{r['distinct_cities']} cities, {r['distinct_stations']} stations")
        L.append(f"- Dropped (all measures null): {r['dropped_all_measures_null']:,}")
        L.append(f"- Dropped (bad/future date): "
                 f"{r['dropped_unparseable_date'] + r['dropped_future_date']:,}")
        L.append(f"- Duplicates removed: {r['duplicates_removed']:,}")
        if r.get("values_nulled_implausible"):
            L.append(f"- Values nulled as implausible: {r['values_nulled_implausible']}")
        L.append(f"- AQI values above scale cap 500 (kept as real severe-episode "
                 f"signal): {r.get('aqi_above_scale_500_kept', 0):,}")
        miss = {k: v for k, v in r["missing_pct_after"].items() if v}
        L.append(f"- Missing % after clean: {miss}")
        L.append("\n  Records per state: " +
                 ", ".join(f"{k} ({v:,})" for k, v in
                           list(r["records_per_state"].items())))
    (VALID / "cleaning_report.md").write_text("\n".join(L), encoding="utf-8")
    print("\nwrote", VALID / "cleaning_report.json")
    print("wrote", VALID / "cleaning_report.md")


if __name__ == "__main__":
    main()
