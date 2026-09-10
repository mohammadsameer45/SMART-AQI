"""ML sanity tests: metrics maths, category mapping, artifact integrity."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from backend.config.aqi_categories import categorize
from backend.ml.evaluate import regression_metrics

ML = Path(__file__).resolve().parents[1] / "ml_models"


def test_categorize_boundaries():
    assert categorize(0) == "Good"
    assert categorize(50) == "Good"
    assert categorize(51) == "Satisfactory"
    assert categorize(200) == "Moderate"
    assert categorize(201) == "Poor"
    assert categorize(450) == "Severe"
    assert categorize(9999) == "Severe"      # above scale still maps
    assert categorize(None) is None
    assert categorize(-5) is None


def test_regression_metrics_perfect():
    y = np.array([10.0, 50.0, 120.0, 300.0])
    m = regression_metrics(y, y.copy())
    assert m["MAE"] == 0 and m["RMSE"] == 0 and m["R2"] == 1.0


def test_regression_metrics_known():
    y = np.array([100.0, 200.0, 300.0])
    p = np.array([110.0, 190.0, 330.0])
    m = regression_metrics(y, p)
    assert m["MAE"] == pytest.approx(16.667, abs=1e-2)   # (10+10+30)/3
    assert m["RMSE"] == pytest.approx(19.149, abs=1e-2)  # sqrt((100+100+900)/3)
    assert 0 < m["R2"] < 1


def test_model_metrics_artifact():
    p = ML / "model_metrics.json"
    if not p.exists():
        pytest.skip("models not trained")
    r = json.loads(p.read_text())
    names = {m["model_name"] for m in r["models"]}
    assert names == {"baseline", "lstm", "gru", "transformer"}
    assert r["best_model"] in names
    # best model really has the lowest validation MAE
    best_val = next(m["val_MAE"] for m in r["models"]
                    if m["model_name"] == r["best_model"])
    assert best_val == min(m["val_MAE"] for m in r["models"])
    for m in r["models"]:
        assert 0 <= m["MAE"] < 200 and -1 <= m["R2"] <= 1


def test_feature_config_split_no_overlap():
    p = ML / "feature_config.json"
    if not p.exists():
        pytest.skip("dataset not built")
    cfg = json.loads(p.read_text())
    assert cfg["split"]["train_end"] < cfg["split"]["val_end"]
    assert cfg["n_stations"] > 0
    assert cfg["seq_window"] >= 7


def test_sequence_shapes():
    p = Path(__file__).resolve().parents[2] / "data" / "processed" / "seq_test.npz"
    if not p.exists():
        pytest.skip("sequences not built")
    d = np.load(p)
    assert d["X"].ndim == 3 and d["X"].shape[1] >= 7
    assert d["X"].shape[0] == d["y"].shape[0] == d["station"].shape[0]
    assert np.isfinite(d["X"]).all()


def test_nn_seeding_is_reproducible():
    """reseed() must give byte-identical RNG draws, so training runs match."""
    pytest.importorskip("tensorflow")
    import numpy as np
    from backend.ml import nn_common
    assert nn_common.SEED == 42
    nn_common.reseed()
    a = (np.random.rand(5).tolist(),
         nn_common.tf.random.normal([5], seed=None).numpy().tolist())
    nn_common.reseed()
    b = (np.random.rand(5).tolist(),
         nn_common.tf.random.normal([5], seed=None).numpy().tolist())
    assert a == b


def test_recursive_forecast_shape_and_dates():
    """The best model rolls forward exactly 7 finite, strictly-dated steps."""
    proc = Path(__file__).resolve().parents[2] / "data" / "processed"
    if not (proc / "feature_table.parquet").exists() or not (ML / "model_metrics.json").exists():
        pytest.skip("models / features not built")
    import json
    import joblib
    import pandas as pd
    from backend.ml.forecast import recursive_forecast
    from backend.ml.preprocessing import SEQ_FEATURES

    cfg = json.loads((proc / "feature_config.json").read_text())
    scalers = joblib.load(proc / "scalers.joblib")
    best = json.loads((ML / "model_metrics.json").read_text())["best_model"]
    flat = pd.read_parquet(proc / "feature_table.parquet")

    sid = next(iter(cfg["station_index"]))
    cols = ["date", "AQI"] + [c for c in cfg["feature_cols"] + SEQ_FEATURES]
    cols = list(dict.fromkeys(c for c in cols if c in flat.columns))
    hist = flat[flat.station_id == sid][cols].copy()

    days = recursive_forecast(best, hist, scalers, cfg, cfg["station_index"][sid])
    assert len(days) == 7
    vals = [v for _, v in days]
    assert all(np.isfinite(v) and 0 <= v < 1000 for v in vals)
    dates = [d for d, _ in days]
    assert all(dates[i] < dates[i + 1] for i in range(6))
