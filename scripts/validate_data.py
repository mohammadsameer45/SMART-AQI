"""
validate_data.py  -  Phase 5 automated validation for SMART AQI.

Runs a battery of checks over the cleaned tables in data/cleaned/ and writes a
pass/warn/fail report to data/validation/. Does not modify data. Exit code is
non-zero if any check FAILs, so it can gate the pipeline / CI.

Checks (docs/architecture.md section 13, brief section 48):
  - AQI >= 0 and not absurd
  - every pollutant column is numeric
  - dates parse, fall inside the expected window, none in the future
  - state and city are non-empty
  - no duplicate rows on the natural key
  - no residual out-of-range concentrations
  - AQI_bucket is a valid CPCB label and consistent with AQI
  - unit sanity (median of each pollutant within a plausible band)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config.aqi_categories import categorize, AQI_CATEGORIES  # noqa: E402

CLEAN = ROOT / "data" / "cleaned"
VALID = ROOT / "data" / "validation"
VALID.mkdir(parents=True, exist_ok=True)

POLLUTANTS = ["PM25", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3",
              "Benzene", "Toluene", "Xylene"]
CONC_MAX = {"PM25": 1000, "PM10": 2000, "NO": 500, "NO2": 500, "NOx": 600,
            "NH3": 500, "CO": 50, "SO2": 500, "O3": 800, "Benzene": 500,
            "Toluene": 500, "Xylene": 500}
# plausible band for the *median* of each pollutant (unit-consistency guard)
MEDIAN_BAND = {"PM25": (5, 300), "PM10": (10, 500), "NO2": (2, 150),
               "SO2": (1, 120), "O3": (2, 150), "CO": (0.1, 10)}
DATE_MIN, DATE_MAX = pd.Timestamp("2015-01-01"), pd.Timestamp("2020-07-02")
VALID_LABELS = {c["label"] for c in AQI_CATEGORIES}

FILES = ["city_day.csv.gz", "station_day.csv.gz",
         "city_hour.csv.gz", "station_hour.csv.gz"]


def check(results: list, name: str, ok: bool, detail: str, warn: bool = False):
    status = "PASS" if ok else ("WARN" if warn else "FAIL")
    results.append({"check": name, "status": status, "detail": detail})
    print(f"    [{status}] {name} - {detail}")


def validate_file(fname: str) -> list:
    df = pd.read_csv(CLEAN / fname, low_memory=False)
    r: list = []
    n = len(df)

    # geography
    check(r, "state_non_empty", df["state"].notna().all(),
          f"{int(df['state'].isna().sum())} rows with null state", warn=True)
    check(r, "city_non_empty", df["city"].notna().all(),
          f"{int(df['city'].isna().sum())} rows with null city")

    # dates
    dt = pd.to_datetime(df["date"], errors="coerce")
    check(r, "dates_parse", dt.notna().all(),
          f"{int(dt.isna().sum())} unparseable")
    check(r, "dates_in_window",
          bool(((dt >= DATE_MIN) & (dt <= DATE_MAX)).all()),
          f"range {dt.min()} .. {dt.max()}")
    check(r, "no_future_dates", bool((dt <= pd.Timestamp.now()).all()),
          f"{int((dt > pd.Timestamp.now()).sum())} future rows")

    # numeric
    non_numeric = [c for c in POLLUTANTS + ["AQI"]
                   if not pd.api.types.is_numeric_dtype(df[c])]
    check(r, "pollutants_numeric", not non_numeric,
          f"non-numeric cols: {non_numeric or 'none'}")

    # AQI sanity
    aqi = pd.to_numeric(df["AQI"], errors="coerce")
    check(r, "aqi_non_negative", bool((aqi.dropna() >= 0).all()),
          f"{int((aqi < 0).sum())} negative AQI")
    check(r, "aqi_within_hard_max", bool((aqi.dropna() <= 1000).all()),
          f"{int((aqi > 1000).sum())} AQI > 1000")
    check(r, "aqi_above_scale_note", True,
          f"{int((aqi > 500).sum())} AQI in 501..1000 (kept as real)", warn=True)

    # residual concentration outliers
    resid = {c: int(((df[c] < 0) | (df[c] > CONC_MAX[c])).sum())
             for c in POLLUTANTS}
    resid = {k: v for k, v in resid.items() if v}
    check(r, "no_residual_conc_outliers", not resid, f"{resid or 'none'}")

    # CO column mis-fill artifact (should have been nulled in cleaning)
    co_no = int((df["CO"].notna() & df["NO"].notna() & (df["CO"] == df["NO"])).sum())
    check(r, "no_co_equals_no_misfill", co_no == 0,
          f"{co_no} rows with CO exactly == NO")

    # duplicates
    key = ["station_id", "date"] if df["station_id"].notna().any() else ["city", "date"]
    dups = int(df.duplicated(subset=key).sum())
    check(r, "no_duplicate_keys", dups == 0, f"{dups} dup rows on {key}")

    # AQI bucket validity + consistency
    bkt = df["AQI_bucket"].dropna()
    bad_labels = sorted(set(bkt.unique()) - VALID_LABELS)
    check(r, "bucket_labels_valid", not bad_labels, f"unexpected: {bad_labels or 'none'}")
    both = df.dropna(subset=["AQI", "AQI_bucket"])
    mism = int((both["AQI"].map(categorize) != both["AQI_bucket"]).sum())
    check(r, "bucket_matches_aqi", mism == 0,
          f"{mism}/{len(both)} rows where bucket != categorize(AQI)", warn=mism < 0.001 * n)

    # unit consistency (median band)
    off = {}
    for c, (lo, hi) in MEDIAN_BAND.items():
        m = float(pd.to_numeric(df[c], errors="coerce").median())
        if m == m and not (lo <= m <= hi):
            off[c] = round(m, 2)
    check(r, "unit_consistency", not off, f"median out of band: {off or 'none'}")

    return r


def main() -> None:
    report = {"files": {}}
    any_fail = False
    for f in FILES:
        print(f"\n  {f}")
        res = validate_file(f)
        report["files"][f] = res
        any_fail |= any(c["status"] == "FAIL" for c in res)

    (VALID / "validation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")

    L = ["# SMART AQI - Data Validation Report\n",
         "_Generated by `scripts/validate_data.py`. FAIL blocks the pipeline; "
         "WARN is advisory._\n"]
    for f, res in report["files"].items():
        L.append(f"\n## `{f}`\n")
        L.append("| Check | Status | Detail |")
        L.append("|---|---|---|")
        for c in res:
            L.append(f"| {c['check']} | {c['status']} | {c['detail']} |")
    (VALID / "validation_report.md").write_text("\n".join(L), encoding="utf-8")
    print("\nwrote", VALID / "validation_report.md")

    if any_fail:
        print("\nVALIDATION FAILED")
        sys.exit(1)
    print("\nvalidation passed (WARNs may remain)")


if __name__ == "__main__":
    main()
