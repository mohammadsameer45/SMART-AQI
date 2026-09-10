"""
audit_raw_data.py  -  Phase 3 raw-data audit for SMART AQI.

Profiles the five CSVs in data/raw/ (Kaggle "Air Quality Data in India
2015-2020") without modifying them. Produces:
  - data/validation/raw_audit.json    machine-readable profile
  - data/validation/raw_audit.md      human-readable data-quality report

No cleaning, no fabrication - inspection only.
"""
from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
OUT = Path(__file__).resolve().parents[1] / "data" / "validation"
OUT.mkdir(parents=True, exist_ok=True)

PLACEHOLDER_TOKENS = {
    "", "na", "n/a", "nan", "none", "null", "-", "--", "not available",
    "not found", "unknown", "coming soon", "tbd", ".",
}
POLLUTANT_COLS = ["PM2.5", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2",
                  "O3", "Benzene", "Toluene", "Xylene"]
# Physically implausible upper bounds (ug/m3 except CO in mg/m3). Values above
# these are flagged, not dropped, at the audit stage.
PLAUSIBLE_MAX = {
    "PM2.5": 1000, "PM10": 2000, "NO": 500, "NO2": 500, "NOx": 500,
    "NH3": 500, "CO": 50, "SO2": 500, "O3": 800, "Benzene": 500,
    "Toluene": 500, "Xylene": 500, "AQI": 1000,
}


def jsonable(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if math.isnan(x) else float(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x


def profile_frame(name: str, df: pd.DataFrame, date_col: str | None,
                  geo_cols: list[str], key_cols: list[str]) -> dict:
    rep: dict = {"file": name, "rows": int(len(df)), "columns": list(df.columns)}

    # --- missing values per column ---
    miss = {}
    for c in df.columns:
        n_null = int(df[c].isna().sum())
        # string placeholder tokens (only meaningful for object cols)
        n_placeholder = 0
        if df[c].dtype == object:
            lowered = df[c].astype(str).str.strip().str.lower()
            n_placeholder = int(lowered.isin(PLACEHOLDER_TOKENS).sum())
        miss[c] = {
            "null": n_null,
            "null_pct": round(100 * n_null / len(df), 2) if len(df) else 0.0,
            "placeholder_tokens": n_placeholder,
        }
    rep["missing"] = miss

    # --- date range ---
    if date_col and date_col in df.columns:
        dt = pd.to_datetime(df[date_col], errors="coerce")
        rep["date"] = {
            "column": date_col,
            "min": jsonable(dt.min()),
            "max": jsonable(dt.max()),
            "unparseable": int(dt.isna().sum() - df[date_col].isna().sum()),
            "future_dated": int((dt > pd.Timestamp.now()).sum()),
        }

    # --- geo coverage ---
    geo = {}
    for c in geo_cols:
        if c in df.columns:
            vals = df[c].dropna().astype(str).str.strip()
            geo[c] = {
                "distinct": int(vals.nunique()),
                "values": sorted(vals.unique().tolist())[:400],
            }
    rep["geo"] = geo
    if {"State", "City"}.issubset(df.columns):
        pair = (df[["State", "City"]].dropna().astype(str)
                .apply(lambda r: r.str.strip()))
        rep["state_city_pairs"] = int(pair.drop_duplicates().shape[0])

    # --- duplicates on natural key ---
    kc = [c for c in key_cols if c in df.columns]
    if kc:
        rep["duplicate_key_rows"] = int(df.duplicated(subset=kc).sum())
        rep["key_columns"] = kc

    # --- pollutant + AQI stats ---
    stats = {}
    for c in POLLUTANT_COLS + ["AQI"]:
        if c not in df.columns:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        n = int(s.notna().sum())
        d = {
            "present": n,
            "coverage_pct": round(100 * n / len(df), 2) if len(df) else 0.0,
            "min": jsonable(s.min()), "max": jsonable(s.max()),
            "mean": jsonable(s.mean()), "median": jsonable(s.median()),
            "negative": int((s < 0).sum()),
            "zero": int((s == 0).sum()),
        }
        if c in PLAUSIBLE_MAX:
            d["above_plausible_max"] = int((s > PLAUSIBLE_MAX[c]).sum())
        stats[c] = d
    rep["pollutant_stats"] = stats

    # --- AQI vs AQI_Bucket consistency ---
    if {"AQI", "AQI_Bucket"}.issubset(df.columns):
        aqi = pd.to_numeric(df["AQI"], errors="coerce")
        bucket = df["AQI_Bucket"].astype(str).str.strip()
        cpcb = [
            (0, 50, "Good"), (51, 100, "Satisfactory"), (101, 200, "Moderate"),
            (201, 300, "Poor"), (301, 400, "Very Poor"), (401, 10_000, "Severe"),
        ]

        def to_bucket(v):
            if pd.isna(v):
                return None
            for lo, hi, label in cpcb:
                if lo <= v <= hi:
                    return label
            return None

        derived = aqi.map(to_bucket)
        both = derived.notna() & bucket.notna() & (bucket != "nan")
        mism = int((both & (derived != bucket)).sum())
        rep["aqi_bucket_check"] = {
            "rows_with_both": int(both.sum()),
            "mismatches_vs_cpcb": mism,
            "distinct_bucket_labels": sorted(
                bucket[bucket != "nan"].dropna().unique().tolist()),
            "rows_bucket_present_aqi_missing": int(
                (bucket.notna() & (bucket != "nan") & aqi.isna()).sum()),
        }

    # --- per-geo record counts (top/bottom) ---
    grp_col = "City" if "City" in df.columns else (
        "StationId" if "StationId" in df.columns else None)
    if grp_col:
        vc = df[grp_col].astype(str).str.strip().value_counts()
        rep["records_per_" + grp_col.lower()] = {
            "n_groups": int(vc.shape[0]),
            "min": int(vc.min()), "max": int(vc.max()),
            "median": int(vc.median()),
            "smallest_10": vc.tail(10).to_dict(),
        }
    return rep


def main() -> None:
    report: dict = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_zip": "C:/Users/new/Desktop/archive.zip",
        "files": {},
    }

    stations = pd.read_csv(RAW / "stations.csv")
    report["files"]["stations.csv"] = profile_frame(
        "stations.csv", stations, None, ["City", "State", "Status"],
        ["StationId"])
    # station -> (city, state) lookup for cross-file checks
    st_map = stations.set_index("StationId")[["City", "State"]].to_dict("index")

    specs = [
        ("city_day.csv", "Date", ["City"], ["City", "Date"]),
        ("station_day.csv", "Date", ["StationId"], ["StationId", "Date"]),
        ("city_hour.csv", "Datetime", ["City"], ["City", "Datetime"]),
        ("station_hour.csv", "Datetime", ["StationId"],
         ["StationId", "Datetime"]),
    ]
    for fname, dcol, geo, key in specs:
        # hourly files are large; read in one pass with pyarrow-free engine
        df = pd.read_csv(RAW / fname, low_memory=False)
        rep = profile_frame(fname, df, dcol, geo, key)
        if "StationId" in df.columns:
            ids = set(df["StationId"].dropna().unique())
            rep["stationids_not_in_stations_csv"] = sorted(
                str(i) for i in ids - set(st_map))[:50]
            rep["n_stationids"] = len(ids)
        report["files"][fname] = rep
        del df

    (OUT / "raw_audit.json").write_text(
        json.dumps(report, indent=2, default=jsonable), encoding="utf-8")

    # ---------- markdown ----------
    L: list[str] = []
    L.append("# SMART AQI - Raw Data Audit\n")
    L.append(f"_Generated {report['generated_at']} from `archive.zip` "
             "(Kaggle: Air Quality Data in India 2015-2020). "
             "Inspection only - no rows modified._\n")
    for fname, rep in report["files"].items():
        L.append(f"\n## `{fname}`\n")
        L.append(f"- **Rows:** {rep['rows']:,}")
        L.append(f"- **Columns:** {', '.join(rep['columns'])}")
        if "date" in rep:
            d = rep["date"]
            L.append(f"- **Date range:** {d['min']} -> {d['max']} "
                     f"(unparseable: {d['unparseable']}, future: {d['future_dated']})")
        for gc, gi in rep.get("geo", {}).items():
            L.append(f"- **Distinct {gc}:** {gi['distinct']}")
        if "state_city_pairs" in rep:
            L.append(f"- **Distinct State/City pairs:** {rep['state_city_pairs']}")
        if "duplicate_key_rows" in rep:
            L.append(f"- **Duplicate rows on key {rep.get('key_columns')}:** "
                     f"{rep['duplicate_key_rows']:,}")
        if "n_stationids" in rep:
            L.append(f"- **Distinct StationIds:** {rep['n_stationids']} "
                     f"(not in stations.csv: {len(rep['stationids_not_in_stations_csv'])})")
        if "aqi_bucket_check" in rep:
            a = rep["aqi_bucket_check"]
            L.append(f"- **AQI vs AQI_Bucket:** {a['mismatches_vs_cpcb']:,} "
                     f"mismatches vs CPCB scale over {a['rows_with_both']:,} rows; "
                     f"labels = {a['distinct_bucket_labels']}")
        # missing-value table
        L.append("\n| Column | Null % | Placeholder tokens |")
        L.append("|---|---:|---:|")
        for c, mi in rep["missing"].items():
            if mi["null"] or mi["placeholder_tokens"]:
                L.append(f"| {c} | {mi['null_pct']} | {mi['placeholder_tokens']} |")
        # pollutant table
        if rep.get("pollutant_stats"):
            L.append("\n| Field | Coverage % | Min | Max | Mean | Neg | > plausible |")
            L.append("|---|---:|---:|---:|---:|---:|---:|")
            for c, s in rep["pollutant_stats"].items():
                L.append(f"| {c} | {s['coverage_pct']} | {s['min']} | {s['max']} "
                         f"| {round(s['mean'], 1) if s['mean'] is not None else None} "
                         f"| {s['negative']} | {s.get('above_plausible_max', '-')} |")
    (OUT / "raw_audit.md").write_text("\n".join(L), encoding="utf-8")
    print("wrote", OUT / "raw_audit.json")
    print("wrote", OUT / "raw_audit.md")


if __name__ == "__main__":
    main()
