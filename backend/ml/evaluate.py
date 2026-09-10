"""Regression metrics for SMART AQI models, computed on the real AQI scale."""
from __future__ import annotations

import numpy as np


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                       mape_floor: float = 20.0) -> dict[str, float]:
    """MAE, RMSE, R2, MAPE on real AQI units.

    MAPE uses a floor on the denominator so that near-zero AQI days (rare, but
    they exist) do not blow the percentage up; the floor is reported so the
    number stays interpretable.
    """
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_pred = np.asarray(y_pred, dtype=float).ravel()
    m = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[m], y_pred[m]
    err = y_pred - y_true

    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    ss_res = float(np.sum(err ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    denom = np.maximum(np.abs(y_true), mape_floor)
    mape = float(np.mean(np.abs(err) / denom) * 100.0)

    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3),
            "R2": round(r2, 4), "MAPE": round(mape, 3),
            "n": int(len(y_true)), "mape_floor": mape_floor}


def residual_quantiles_by_horizon(residuals_by_h: dict[int, np.ndarray]
                                  ) -> dict[int, dict[str, float]]:
    """Per-horizon residual spread, used to draw forecast uncertainty bands."""
    out = {}
    for h, res in residuals_by_h.items():
        res = np.asarray(res, dtype=float)
        res = res[np.isfinite(res)]
        if res.size == 0:
            out[h] = {"lo": 0.0, "hi": 0.0, "std": 0.0}
            continue
        out[h] = {"lo": float(np.percentile(res, 10)),
                  "hi": float(np.percentile(res, 90)),
                  "std": float(np.std(res))}
    return out
