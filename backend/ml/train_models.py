"""
train_models.py  -  Phase 8-10 training orchestrator for SMART AQI.

  1  build (or load) the ML-ready dataset            backend.ml.preprocessing
  2  chronological train / val / test  (no shuffling, scalers fit on train)
  3  train  baseline (XGBoost) + LSTM + GRU + Transformer
  4  evaluate every model on the held-out test period (MAE / RMSE / R2 / MAPE)
  5  pick the best model by VALIDATION MAE (never hard-coded)
  6  persist models, scalers, feature config, model_metrics.json
  7  seed  model_metrics  in MongoDB
  8  generate sample recursive 7-day forecasts with the best model and seed
     forecast_records

Run:  python -m backend.ml.train_models  [--epochs N] [--forecast-stations K]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from backend.config.aqi_categories import categorize  # noqa: E402
from backend.ml import baseline_model as base  # noqa: E402
from backend.ml import nn_common  # noqa: E402
from backend.ml.evaluate import regression_metrics  # noqa: E402
from backend.ml.preprocessing import (PROCESSED, SEQ_FEATURES, SEQ_WINDOW,  # noqa: E402
                                      make_dataset)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "ml_models"
OUT.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------- helpers
def _load_seq(split: str):
    d = np.load(PROCESSED / f"seq_{split}.npz")
    return d["X"], d["station"], d["y"]


def _nn_data():
    Xtr, Str, ytr = _load_seq("train")
    Xva, Sva, yva = _load_seq("val")
    Xte, Ste, yte = _load_seq("test")
    return dict(Xtr=Xtr, Str=Str, ytr=ytr, Xva=Xva, Sva=Sva, yva=yva,
               Xte=Xte, Ste=Ste, yte=yte)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--rebuild", action="store_true",
                    help="rebuild the feature dataset before training")
    ap.add_argument("--forecast-stations", type=int, default=8)
    ap.add_argument("--no-seed", action="store_true",
                    help="skip writing to MongoDB")
    args = ap.parse_args()

    t0 = time.time()
    if args.rebuild or not (PROCESSED / "feature_config.json").exists():
        print("building dataset ...")
        make_dataset(save=True)
    cfg = json.loads((PROCESSED / "feature_config.json").read_text())
    scalers = joblib.load(PROCESSED / "scalers.joblib")
    tgt = scalers["target"]
    flat = pd.read_parquet(PROCESSED / "feature_table.parquet")
    feat_cols = cfg["feature_cols"]
    n_stations = cfg["n_stations"]
    print(f"stations={n_stations}  flat rows={cfg['rows']}  seq rows={cfg['seq_rows']}")
    print(f"split: train<= {cfg['split']['train_end']} | val<= {cfg['split']['val_end']} | test {cfg['split']['test']}")

    metrics: list[dict] = []
    preds_test: dict[str, np.ndarray] = {}
    val_mae: dict[str, float] = {}

    # ---------------------------------------------------------- 1) baseline ---
    print("\n=== baseline (%s) ===" % base.BACKEND)
    Xb = flat[feat_cols + ["station_idx"]].astype(float)
    yb = flat["target_AQI"].astype(float).to_numpy()
    tr, va, te = (flat.split == "train").to_numpy(), (flat.split == "val").to_numpy(), (flat.split == "test").to_numpy()
    ts = time.time()
    bmodel = base.fit(base.build(), Xb[tr], yb[tr], Xb[va], yb[va])
    bt = time.time() - ts
    p_te = np.asarray(bmodel.predict(Xb[te]), dtype=float)
    p_va = np.asarray(bmodel.predict(Xb[va]), dtype=float)
    preds_test["baseline"] = p_te
    val_mae["baseline"] = float(np.mean(np.abs(p_va - yb[va])))
    m = regression_metrics(yb[te], p_te)
    fi = base.feature_importance(bmodel, feat_cols + ["station_idx"])
    metrics.append({"model_name": "baseline", "backend": base.BACKEND,
                    "training_time_s": round(bt, 1), **m,
                    "val_MAE": round(val_mae["baseline"], 3),
                    "feature_importance": fi})
    joblib.dump(bmodel, OUT / "baseline_model.joblib")
    print(f"  {bt:.1f}s  test MAE={m['MAE']} RMSE={m['RMSE']} R2={m['R2']} MAPE={m['MAPE']}%")
    print("  top features:", list(fi.items())[:6])

    # ----------------------------------------------------- 2) sequence nets ---
    D = _nn_data()
    yte_real = tgt.inverse_transform(D["yte"].reshape(-1, 1)).ravel()
    yva_real = tgt.inverse_transform(D["yva"].reshape(-1, 1)).ravel()
    for name in ("lstm", "gru", "transformer"):
        print(f"\n=== {name} ===")
        model = nn_common.build(name, SEQ_WINDOW, len(SEQ_FEATURES), n_stations)
        ts = time.time()
        nn_common.train_nn(name, model, D, OUT / f"{name}_model.keras",
                           epochs=args.epochs, verbose=2)
        tt = time.time() - ts
        p_te = tgt.inverse_transform(
            nn_common.predict_nn(model, D["Xte"], D["Ste"]).reshape(-1, 1)).ravel()
        p_va = tgt.inverse_transform(
            nn_common.predict_nn(model, D["Xva"], D["Sva"]).reshape(-1, 1)).ravel()
        preds_test[name] = p_te
        val_mae[name] = float(np.mean(np.abs(p_va - yva_real)))
        m = regression_metrics(yte_real, p_te)
        metrics.append({"model_name": name, "backend": "tensorflow.keras",
                        "training_time_s": round(tt, 1), **m,
                        "val_MAE": round(val_mae[name], 3)})
        print(f"  {tt:.1f}s  test MAE={m['MAE']} RMSE={m['RMSE']} R2={m['R2']} MAPE={m['MAPE']}%")

    # ------------------------------------------------------- 3) select best ---
    best = min(val_mae, key=val_mae.get)
    for mrec in metrics:
        mrec["is_best"] = (mrec["model_name"] == best)
        mrec["split"] = cfg["split"]
        mrec["training_date"] = pd.Timestamp.utcnow().isoformat()
        mrec["n_train"] = cfg["seq_rows"]["train"] if mrec["model_name"] != "baseline" else cfg["rows"]["train"]
        mrec["n_val"] = cfg["seq_rows"]["val"] if mrec["model_name"] != "baseline" else cfg["rows"]["val"]
        mrec["n_test"] = cfg["seq_rows"]["test"] if mrec["model_name"] != "baseline" else cfg["rows"]["test"]

    # one-step test residual std of the best model -> forecast band
    resid_std = float(np.std(preds_test[best] - (yb[te] if best == "baseline" else yte_real)))

    joblib.dump(scalers, OUT / "scalers.joblib")
    (OUT / "feature_config.json").write_text(json.dumps(cfg, indent=2))
    report = {"generated_at": pd.Timestamp.utcnow().isoformat(),
              "best_model": best, "selection_metric": "validation MAE",
              "resid_std_best": round(resid_std, 3), "models": metrics}
    (OUT / "model_metrics.json").write_text(json.dumps(report, indent=2))

    print("\n================ MODEL COMPARISON ================")
    print(f"{'model':<12}{'val MAE':>9}{'test MAE':>10}{'RMSE':>9}{'R2':>8}{'MAPE%':>8}{'train s':>9}")
    for mrec in metrics:
        star = "  <- best" if mrec["is_best"] else ""
        print(f"{mrec['model_name']:<12}{mrec['val_MAE']:>9}{mrec['MAE']:>10}"
              f"{mrec['RMSE']:>9}{mrec['R2']:>8}{mrec['MAPE']:>8}{mrec['training_time_s']:>9}{star}")

    # --------------------------------------------------------- 4) persist DB --
    if not args.no_seed:
        try:
            _seed_metrics(report)
            _seed_sample_forecasts(best, flat, cfg, scalers, resid_std,
                                   args.forecast_stations)
        except Exception as e:                                  # pragma: no cover
            print("  [warn] MongoDB seeding skipped:", e)

    print(f"\ndone in {time.time() - t0:.0f}s  ->  {OUT}")


# ------------------------------------------------------------ DB seed helpers
def _seed_metrics(report: dict) -> None:
    from pymongo import ReplaceOne
    from backend.models import mongo_models as M
    ops = []
    for mrec in report["models"]:
        _id = f"{mrec['model_name']}:{report['generated_at'][:10]}"
        ops.append(ReplaceOne({"_id": _id}, {"_id": _id, **mrec,
                   "run_generated_at": report["generated_at"]}, upsert=True))
    M.col(M.MODEL_METRICS).bulk_write(ops, ordered=False)
    print(f"  seeded model_metrics: {len(ops)} rows "
          f"(best = {report['best_model']})")


def _recursive_forecast(best: str, hist: pd.DataFrame, scalers: dict,
                        cfg: dict, station_idx: int, horizon: int = 7):
    """Roll the best model forward `horizon` days for one station.

    Pollutant channels are held at their last observed daily value (a documented
    limitation - a full forecast would couple a pollutant model); calendar
    channels advance for real; the predicted AQI feeds back as the next lag.
    """
    tgt = scalers["target"]
    last = hist.sort_values("date").iloc[-1]
    cur_date = pd.Timestamp(last["date"])
    aqi_series = list(hist.sort_values("date")["AQI"].astype(float).values)
    out = []

    if best == "baseline":
        bmodel = joblib.load(OUT / "baseline_model.joblib")
        feat_cols = cfg["feature_cols"]
        persist = {c: float(last[c]) if pd.notna(last[c]) else 0.0
                   for c in feat_cols if c in last}
        for h in range(1, horizon + 1):
            cur_date += timedelta(days=1)
            a = np.array([x for x in aqi_series if np.isfinite(x)], dtype=float)
            row = dict(persist)
            row["AQI_lag_1"] = a[-1]
            row["AQI_lag_2"] = a[-2] if len(a) > 1 else a[-1]
            row["AQI_lag_3"] = a[-3] if len(a) > 2 else a[-1]
            row["AQI_lag_7"] = a[-7] if len(a) > 6 else a[-1]
            row["AQI_roll_mean_3"] = float(np.mean(a[-3:]))
            row["AQI_roll_mean_7"] = float(np.mean(a[-7:]))
            row["AQI_roll_std_7"] = float(np.std(a[-7:]))
            row["dow"] = cur_date.dayofweek
            row["month"] = cur_date.month
            doy = cur_date.dayofyear
            row["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
            row["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
            for s in ("winter", "summer", "monsoon", "post_monsoon"):
                row[f"seas_{s}"] = 0.0
            X = pd.DataFrame([[row.get(c, 0.0) for c in feat_cols] + [station_idx]],
                             columns=feat_cols + ["station_idx"])
            pred = float(bmodel.predict(X)[0])
            aqi_series.append(pred)
            out.append((cur_date, max(pred, 0.0)))
        return out

    # sequence model
    import tensorflow as tf
    model = tf.keras.models.load_model(OUT / f"{best}_model.keras")
    seq_scaler, seq_med = scalers["sequence"], scalers["seq_median"]
    W = SEQ_WINDOW
    g = hist.sort_values("date").tail(W + 3).copy()
    chan = g[SEQ_FEATURES].astype(float).fillna(pd.Series(seq_med))
    buf = chan.to_numpy()[-W:].tolist()
    persist_poll = {c: (float(g[c].iloc[-1]) if pd.notna(g[c].iloc[-1])
                        else seq_med[c])
                    for c in SEQ_FEATURES if c not in ("AQI", "doy_sin", "doy_cos", "dow")}
    for h in range(1, horizon + 1):
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


def _seed_sample_forecasts(best, flat, cfg, scalers, resid_std, k) -> None:
    from pymongo import ReplaceOne
    from backend.models import mongo_models as M

    st_idx = cfg["station_index"]
    idx2sid = {v: k for k, v in st_idx.items()}
    # stations with the most recent test-period coverage
    recent = (flat[flat.split == "test"].groupby("station_id")["target_AQI"]
              .count().sort_values(ascending=False).head(k).index.tolist())
    gen_at = pd.Timestamp.utcnow().isoformat()
    ops = []
    z = 1.2816  # ~80% band
    for sid in recent:
        loc = M.col(M.LOCATIONS).find_one({"_id": f"station:{sid}"})
        hist = flat[flat.station_id == sid][["date", "AQI"] + cfg["feature_cols"]].copy()
        if len(hist) < SEQ_WINDOW + 3:
            continue
        fc = _recursive_forecast(best, hist, scalers, cfg, st_idx[sid])
        for h, (d, val) in enumerate(fc, start=1):
            band = z * resid_std * np.sqrt(h)
            _id = f"{sid}:{best}:{gen_at[:10]}:{h}"
            ops.append(ReplaceOne({"_id": _id}, {
                "_id": _id, "level": "station",
                "state": loc["state"] if loc else None,
                "city": loc["city"] if loc else None,
                "district": None, "station_id": sid,
                "model": best, "generated_at": gen_at, "horizon_day": h,
                "forecast_date": d.strftime("%Y-%m-%d"),
                "predicted_AQI": round(float(val), 1),
                "AQI_bucket": categorize(val),
                "lower": round(float(max(val - band, 0)), 1),
                "upper": round(float(val + band), 1),
                "is_prediction": True,
                "method": "recursive multi-step; pollutant channels persisted",
            }, upsert=True))
    if ops:
        M.col(M.FORECAST_RECORDS).bulk_write(ops, ordered=False)
    print(f"  seeded forecast_records: {len(ops)} rows "
          f"({len(recent)} stations x 7 days, model={best})")


if __name__ == "__main__":
    main()
