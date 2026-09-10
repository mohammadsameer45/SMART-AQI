"""
Strong tabular baseline for SMART AQI: gradient-boosted trees (XGBoost) on the
flat lag / rolling / calendar / pollutant feature table. Provides the
comparison point for the sequence models and yields feature importances for the
Model Insights page (importance != causation).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from xgboost import XGBRegressor
    _HAS_XGB = True
except Exception:                                    # pragma: no cover
    from sklearn.ensemble import GradientBoostingRegressor
    _HAS_XGB = False


def build():
    if _HAS_XGB:
        return XGBRegressor(
            n_estimators=800, max_depth=6, learning_rate=0.03,
            subsample=0.9, colsample_bytree=0.9, min_child_weight=3,
            reg_lambda=1.0, objective="reg:squarederror",
            n_jobs=0, random_state=42, early_stopping_rounds=50,
        )
    return GradientBoostingRegressor(random_state=42)   # fallback


def fit(model, Xtr: pd.DataFrame, ytr: np.ndarray,
        Xva: pd.DataFrame, yva: np.ndarray):
    if _HAS_XGB:
        model.fit(Xtr, ytr, eval_set=[(Xva, yva)], verbose=False)
    else:
        model.fit(Xtr, ytr)
    return model


def feature_importance(model, feature_cols: list[str]) -> dict[str, float]:
    imp = getattr(model, "feature_importances_", None)
    if imp is None:
        return {}
    imp = np.asarray(imp, dtype=float)
    if imp.sum() > 0:
        imp = imp / imp.sum()
    return {c: round(float(v), 5)
            for c, v in sorted(zip(feature_cols, imp),
                               key=lambda kv: kv[1], reverse=True)}


BACKEND = "xgboost" if _HAS_XGB else "sklearn_gbr"
