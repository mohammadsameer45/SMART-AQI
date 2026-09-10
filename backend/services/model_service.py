"""Model comparison + per-model insight payloads for the Model Insights page."""
from __future__ import annotations

import json

from backend.config import config
from backend.models import mongo_models as M
from backend.utils.responses import ApiError

_MODELS = ["baseline", "lstm", "gru", "transformer"]


def metrics() -> dict:
    rows = list(M.col(M.MODEL_METRICS).find({}, {"_id": 0})
                .sort("training_date", -1))
    # newest run per model
    seen: dict[str, dict] = {}
    for r in rows:
        seen.setdefault(r["model_name"], r)
    latest = list(seen.values())
    best = next((r["model_name"] for r in latest if r.get("is_best")), None)
    order = {"MAE": 1}
    latest.sort(key=lambda r: r.get("MAE", 1e9))
    return {
        "models": latest,
        "best_model": best,
        "selection_metric": "validation MAE",
        "columns": ["model_name", "MAE", "RMSE", "R2", "MAPE",
                    "training_time_s", "val_MAE"],
        "note": "Best model is chosen automatically by lowest validation MAE.",
    }


def insights(model: str) -> dict:
    if model not in _MODELS:
        raise ApiError("unknown_model",
                       f"model must be one of {_MODELS}", 404)
    mrec = M.col(M.MODEL_METRICS).find_one({"model_name": model}, {"_id": 0},
                                           sort=[("training_date", -1)])
    if not mrec:
        raise ApiError("not_trained", f"{model} has no metrics yet", 404)

    path = config.ML_MODELS_DIR / f"insights_{model}.json"
    avp = json.loads(path.read_text()) if path.exists() else None
    return {
        "model": model,
        "metrics": {k: mrec.get(k) for k in
                    ("MAE", "RMSE", "R2", "MAPE", "val_MAE",
                     "training_time_s", "backend", "is_best")},
        "split": mrec.get("split"),
        "feature_importance": mrec.get("feature_importance"),
        "actual_vs_predicted": (avp or {}).get("points"),
        "error_hist": (avp or {}).get("error_hist"),
        "avp_note": None if avp else
        "Run `python -m backend.ml.export_insights` to generate the "
        "actual-vs-predicted sample.",
    }
