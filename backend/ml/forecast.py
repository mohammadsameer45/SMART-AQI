"""
Recursive multi-step 7-day AQI forecasting for SMART AQI.

One reusable path for both the training run's sample forecasts and the
standalone `scripts/generate_forecasts.py` that fills `forecast_records` for
every station with enough recent daily history.

Assumptions (documented in docs/forecasting.md):
  * daily resolution, rolled forward one step at a time
  * calendar channels (dow, day-of-year sin/cos) advance for real
  * pollutant channels are held at the last observed daily value
  * predicted AQI feeds back as the next lag / sequence input
  * uncertainty band = z * resid_std * sqrt(horizon), clipped at 0
"""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.config import config
from backend.config.aqi_categories import categorize
from backend.ml.preprocessing import PROCESSED, SEQ_FEATURES, SEQ_WINDOW

OUT = config.ML_MODELS_DIR
Z_80 = 1.2816            # ~80% band under a normal approximation
_SEASONS = ("winter", "summer", "monsoon", "post_monsoon")


def _load_artifacts():
    cfg = json.loads((PROCESSED / "feature_config.json").read_text())
    scalers = joblib.load(PROCESSED / "scalers.joblib")
    report = json.loads((OUT / "model_metrics.json").read_text())
    return cfg, scalers, report


def recursive_forecast(model_name: str, hist: pd.DataFrame, scalers: dict,
                       cfg: dict, station_idx: int, horizon: int = 7,
                       _cache: dict | None = None):
    """Return [(date, predicted_AQI), ...] of length `horizon` for one station.

    `hist` must have columns: date, AQI, and every name in cfg["feature_cols"]
    (for the baseline) / SEQ_FEATURES (for the sequence models), sorted or not.
    """
    tgt = scalers["target"]
    h = hist.sort_values("date")
    last = h.iloc[-1]
    cur_date = pd.Timestamp(last["date"])
    aqi_series = list(h["AQI"].astype(float).values)
    out: list[tuple[pd.Timestamp, float]] = []
    cache = _cache if _cache is not None else {}

    if model_name == "baseline":
        bmodel = cache.get("baseline")
        if bmodel is None:
            bmodel = cache["baseline"] = joblib.load(OUT / "baseline_model.joblib")
        feat_cols = cfg["feature_cols"]
        persist = {c: (float(last[c]) if c in last and pd.notna(last[c]) else 0.0)
                   for c in feat_cols}
        for step in range(1, horizon + 1):
            cur_date += timedelta(days=1)
            a = np.array([x for x in aqi_series if np.isfinite(x)], dtype=float)
            if a.size == 0:
                a = np.array([100.0])
            row = dict(persist)
            row["AQI_lag_1"] = a[-1]
            row["AQI_lag_2"] = a[-2] if a.size > 1 else a[-1]
            row["AQI_lag_3"] = a[-3] if a.size > 2 else a[-1]
            row["AQI_lag_7"] = a[-7] if a.size > 6 else a[-1]
            row["AQI_roll_mean_3"] = float(np.mean(a[-3:]))
            row["AQI_roll_mean_7"] = float(np.mean(a[-7:]))
            row["AQI_roll_std_7"] = float(np.std(a[-7:]))
            row["dow"] = cur_date.dayofweek
            row["month"] = cur_date.month
            doy = cur_date.dayofyear
            row["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
            row["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
            for s in _SEASONS:
                row[f"seas_{s}"] = 0.0
            X = pd.DataFrame([[row.get(c, 0.0) for c in feat_cols] + [station_idx]],
                             columns=feat_cols + ["station_idx"])
            pred = float(bmodel.predict(X)[0])
            aqi_series.append(pred)
            out.append((cur_date, max(pred, 0.0)))
        return out

    # ---- sequence model (lstm / gru / transformer) ----
    import tensorflow as tf
    model = cache.get(model_name)
    if model is None:
        model = cache[model_name] = tf.keras.models.load_model(
            OUT / f"{model_name}_model.keras")
    seq_scaler, seq_med = scalers["sequence"], scalers["seq_median"]
    W = SEQ_WINDOW
    g = h.tail(W + 3).copy()
    buf = g[SEQ_FEATURES].astype(float).fillna(pd.Series(seq_med)).to_numpy()[-W:].tolist()
    persist_poll = {c: (float(g[c].iloc[-1]) if pd.notna(g[c].iloc[-1]) else seq_med[c])
                    for c in SEQ_FEATURES if c not in ("AQI", "doy_sin", "doy_cos", "dow")}
    for step in range(1, horizon + 1):
        cur_date += timedelta(days=1)
        doy = cur_date.dayofyear
        x = seq_scaler.transform(np.array(buf[-W:], dtype=float))
        pred_s = float(model.predict(
            {"seq": x[None, ...], "station": np.array([station_idx])},
            verbose=0).ravel()[0])
        pred = float(tgt.inverse_transform([[pred_s]])[0, 0])
        newrow = []
        for c in SEQ_FEATURES:
            if c == "AQI":
                newrow.append(pred)
            elif c == "doy_sin":
                newrow.append(np.sin(2 * np.pi * doy / 365.25))
            elif c == "doy_cos":
                newrow.append(np.cos(2 * np.pi * doy / 365.25))
            elif c == "dow":
                newrow.append(cur_date.dayofweek)
            else:
                newrow.append(persist_poll[c])
        buf.append(newrow)
        out.append((cur_date, max(pred, 0.0)))
    return out


def forecast_rows(sid: str, loc: dict | None, days, model_name: str,
                  resid_std: float, generated_at: str) -> list[dict]:
    rows = []
    for step, (d, val) in enumerate(days, start=1):
        band = Z_80 * resid_std * np.sqrt(step)
        _id = f"{sid}:{model_name}:{generated_at[:10]}:{step}"
        rows.append({
            "_id": _id, "level": "station",
            "state": (loc or {}).get("state"), "city": (loc or {}).get("city"),
            "district": None, "station_id": sid,
            "model": model_name, "generated_at": generated_at, "horizon_day": step,
            "forecast_date": d.strftime("%Y-%m-%d"),
            "predicted_AQI": round(float(val), 1),
            "AQI_bucket": categorize(val),
            "lower": round(float(max(val - band, 0)), 1),
            "upper": round(float(val + band), 1),
            "is_prediction": True,
            "method": "recursive multi-step; pollutant channels persisted",
        })
    return rows


def generate_all(min_recent: int | None = None, horizon: int = 7,
                 limit: int | None = None) -> dict:
    """Forecast every eligible station and upsert into `forecast_records`."""
    from pymongo import ReplaceOne
    from backend.models import mongo_models as M

    cfg, scalers, report = _load_artifacts()
    best = report["best_model"]
    resid_std = float(report.get("resid_std_best", 25.0))
    need = min_recent or (SEQ_WINDOW + 3)

    flat = pd.read_parquet(PROCESSED / "feature_table.parquet")
    st_idx = cfg["station_index"]
    gen_at = pd.Timestamp.utcnow().isoformat()
    cache: dict = {}

    counts = flat.groupby("station_id")["target_AQI"].count()
    eligible = [s for s in st_idx if counts.get(s, 0) >= need]
    if limit:
        eligible = eligible[:limit]

    wanted = ["date", "AQI"]
    for c in cfg["feature_cols"] + SEQ_FEATURES:
        if c not in wanted:
            wanted.append(c)

    ops, skipped = [], []
    for sid in eligible:
        cols = [c for c in wanted if c in flat.columns]
        hist = flat[flat.station_id == sid][cols].copy()
        if len(hist) < need:
            skipped.append(sid)
            continue
        loc = M.col(M.LOCATIONS).find_one({"_id": f"station:{sid}"})
        days = recursive_forecast(best, hist, scalers, cfg, st_idx[sid],
                                  horizon, _cache=cache)
        for r in forecast_rows(sid, loc, days, best, resid_std, gen_at):
            ops.append(ReplaceOne({"_id": r["_id"]}, r, upsert=True))

    written = 0
    if ops:
        for i in range(0, len(ops), 500):
            res = M.col(M.FORECAST_RECORDS).bulk_write(ops[i:i + 500], ordered=False)
            written += (res.upserted_count or 0) + (res.modified_count or 0)

    return {"model": best, "generated_at": gen_at,
            "stations": len(eligible), "skipped": len(skipped),
            "rows": len(ops), "written_or_updated": written}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--min-recent", type=int, default=None)
    a = ap.parse_args()
    print(json.dumps(generate_all(min_recent=a.min_recent, limit=a.limit), indent=2))
