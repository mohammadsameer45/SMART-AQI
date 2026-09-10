"""
SMART AQI machine-learning package.

IMPORTANT (Windows): TensorFlow's native runtime fails to initialise if XGBoost
(which ships its own OpenMP runtime) is imported first. Importing TensorFlow
here, before anything else in this package, guarantees the correct order for
every entry point (training script, API services, tests).
"""
from __future__ import annotations

import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

try:  # optional: some tooling imports backend.ml without TF installed
    import tensorflow as _tf  # noqa: F401
except Exception:  # pragma: no cover
    _tf = None
