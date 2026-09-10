"""
tune_transformer.py  -  iterate on the time-series Transformer alone.

Loads data/processed/, trains ONLY the transformer with the current
backend/ml/nn_common.build_transformer + train_nn, evaluates on the held-out
test period, and prints the result next to the last recorded run. Does not touch
MongoDB or the other models' artifacts.

  python scripts/tune_transformer.py            # train + evaluate, no save
  python scripts/tune_transformer.py --epochs 40
  python scripts/tune_transformer.py --save     # overwrite transformer_model.keras
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.ml import nn_common  # noqa: E402
from backend.ml.evaluate import regression_metrics  # noqa: E402
from backend.ml.preprocessing import PROCESSED, SEQ_FEATURES, SEQ_WINDOW  # noqa: E402

OUT = ROOT / "backend" / "ml_models"


def _seq(split):
    d = np.load(PROCESSED / f"seq_{split}.npz")
    return d["X"], d["station"], d["y"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    cfg = json.loads((PROCESSED / "feature_config.json").read_text())
    tgt = joblib.load(PROCESSED / "scalers.joblib")["target"]
    Xtr, Str, ytr = _seq("train")
    Xva, Sva, yva = _seq("val")
    Xte, Ste, yte = _seq("test")
    data = dict(Xtr=Xtr, Str=Str, ytr=ytr, Xva=Xva, Sva=Sva, yva=yva)

    model = nn_common.build("transformer", SEQ_WINDOW, len(SEQ_FEATURES),
                            cfg["n_stations"])
    model.summary(line_length=88)
    print(f"\nparams: {model.count_params():,}\n")

    t0 = time.time()
    hist = nn_common.train_nn("transformer", model, data,
                              OUT / "transformer_model.keras" if args.save
                              else ROOT / "data" / "processed" / "_tune_tmp.keras",
                              epochs=args.epochs, verbose=2)
    secs = time.time() - t0

    p_te = tgt.inverse_transform(
        nn_common.predict_nn(model, Xte, Ste).reshape(-1, 1)).ravel()
    p_va = tgt.inverse_transform(
        nn_common.predict_nn(model, Xva, Sva).reshape(-1, 1)).ravel()
    yte_r = tgt.inverse_transform(yte.reshape(-1, 1)).ravel()
    yva_r = tgt.inverse_transform(yva.reshape(-1, 1)).ravel()

    m = regression_metrics(yte_r, p_te)
    val_mae = float(np.mean(np.abs(p_va - yva_r)))
    best_epoch = int(np.argmin(hist.history["val_loss"])) + 1

    prev = None
    mm = OUT / "model_metrics.json"
    if mm.exists():
        for r in json.loads(mm.read_text())["models"]:
            if r["model_name"] == "transformer":
                prev = r

    print("\n================ TRANSFORMER ================")
    print(f"trained {len(hist.history['loss'])} epochs (best @ {best_epoch}) "
          f"in {secs:.0f}s")
    print(f"{'':10}{'val MAE':>10}{'test MAE':>10}{'RMSE':>10}{'R2':>9}{'MAPE':>8}")
    print(f"{'this run':10}{val_mae:>10.3f}{m['MAE']:>10.3f}{m['RMSE']:>10.3f}"
          f"{m['R2']:>9.4f}{m['MAPE']:>8.2f}")
    if prev:
        print(f"{'previous':10}{prev['val_MAE']:>10.3f}{prev['MAE']:>10.3f}"
              f"{prev['RMSE']:>10.3f}{prev['R2']:>9.4f}{prev['MAPE']:>8.2f}")
        d = prev["MAE"] - m["MAE"]
        print(f"\ntest MAE {'improved' if d > 0 else 'worse'} by {abs(d):.3f}")
    if args.save:
        print(f"\nsaved -> {OUT / 'transformer_model.keras'}  "
              "(run train_models.py --rebuild to refresh all metrics/forecasts)")


if __name__ == "__main__":
    main()
