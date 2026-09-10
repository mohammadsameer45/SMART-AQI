"""
export_insights.py  -  actual-vs-predicted samples for the Model Insights page.

Loads each trained model + the held-out test set, runs inference, and writes
backend/ml_models/insights_<model>.json with:
  points     : sampled [{actual, predicted}]  (<= 600)
  error_hist : {bins, counts} of (predicted - actual)

Fast (inference only). Run after training.
"""
from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd

from backend.config import config
from backend.ml import nn_common
from backend.ml.preprocessing import PROCESSED, SEQ_WINDOW, SEQ_FEATURES

OUT = config.ML_MODELS_DIR
SAMPLE = 600


def _hist(err: np.ndarray) -> dict:
    counts, edges = np.histogram(err, bins=30)
    return {"bins": [round(float(e), 1) for e in edges],
            "counts": [int(c) for c in counts]}


def _dump(name: str, actual: np.ndarray, pred: np.ndarray) -> None:
    m = np.isfinite(actual) & np.isfinite(pred)
    actual, pred = actual[m], pred[m]
    idx = np.arange(len(actual))
    if len(idx) > SAMPLE:
        idx = np.random.RandomState(42).choice(idx, SAMPLE, replace=False)
        idx.sort()
    points = [{"actual": round(float(a), 1), "predicted": round(float(p), 1)}
              for a, p in zip(actual[idx], pred[idx])]
    (OUT / f"insights_{name}.json").write_text(json.dumps({
        "n_test": int(len(actual)),
        "points": points,
        "error_hist": _hist(pred - actual),
    }, indent=2))
    print(f"  wrote insights_{name}.json  ({len(points)} points, "
          f"n_test={len(actual)})")


def main() -> None:
    cfg = json.loads((PROCESSED / "feature_config.json").read_text())
    scalers = joblib.load(PROCESSED / "scalers.joblib")
    tgt = scalers["target"]

    # ---- baseline ----
    flat = pd.read_parquet(PROCESSED / "feature_table.parquet")
    te = (flat.split == "test").to_numpy()
    Xb = flat[cfg["feature_cols"] + ["station_idx"]].astype(float)
    yb = flat["target_AQI"].astype(float).to_numpy()
    bmodel = joblib.load(OUT / "baseline_model.joblib")
    _dump("baseline", yb[te], np.asarray(bmodel.predict(Xb[te]), dtype=float))

    # ---- sequence models ----
    d = np.load(PROCESSED / "seq_test.npz")
    Xte, Ste, yte = d["X"], d["station"], d["y"]
    yte_real = tgt.inverse_transform(yte.reshape(-1, 1)).ravel()
    import tensorflow as tf
    for name in ("lstm", "gru", "transformer"):
        p = OUT / f"{name}_model.keras"
        if not p.exists():
            print(f"  skip {name} (no model file)")
            continue
        model = tf.keras.models.load_model(p)
        pred = tgt.inverse_transform(
            nn_common.predict_nn(model, Xte, Ste).reshape(-1, 1)).ravel()
        _dump(name, yte_real, pred)


if __name__ == "__main__":
    main()
