"""Time-series Transformer for SMART AQI.

Learned positional embedding + stacked multi-head self-attention blocks with
feed-forward sublayers, residual connections and layer normalisation, then
global average pooling and a regression head. This is a genuine attention
model, not a dense network relabelled "Transformer".
"""
from backend.ml.nn_common import build_transformer as build, train_nn, predict_nn

__all__ = ["build", "train_nn", "predict_nn"]
