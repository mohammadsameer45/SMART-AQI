"""
Shared building blocks for the SMART AQI sequence models (LSTM / GRU /
Transformer). Each model takes two inputs:

    seq_in  : (window, n_seq_features)  scaled daily sequence
    stn_in  : ()                        integer station index -> Embedding

so a single pooled model serves every station while still learning
station-specific level/behaviour. Real recurrent / attention layers are used -
none of these is a renamed dense network.
"""
from __future__ import annotations

import os
import random as _pyrandom

SEED = int(os.getenv("ML_SEED", "42"))

# these must be set before TensorFlow initialises
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("PYTHONHASHSEED", str(SEED))
os.environ.setdefault("TF_DETERMINISTIC_OPS", "1")

import numpy as np  # noqa: E402
import tensorflow as tf  # noqa: E402
from tensorflow.keras import layers, Model  # noqa: E402

tf.get_logger().setLevel("ERROR")

# Op-level determinism: same hardware + TF version -> bit-identical training
# runs. Costs some speed; reproducibility is the goal here.
try:
    tf.config.experimental.enable_op_determinism()
except Exception:  # pragma: no cover - older TF
    pass


def reseed(seed: int = SEED) -> None:
    """Reset every RNG so each model trains from the same state, regardless of
    run order or what the other models consumed."""
    _pyrandom.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)


reseed(SEED)

STATION_EMB_DIM = 8


def _inputs(window: int, n_feats: int):
    seq_in = layers.Input(shape=(window, n_feats), name="seq")
    stn_in = layers.Input(shape=(), dtype="int32", name="station")
    return seq_in, stn_in


def _station_vec(stn_in, n_stations: int):
    e = layers.Embedding(n_stations, STATION_EMB_DIM, name="station_emb")(stn_in)
    return layers.Flatten()(e)


def _head(x, stn_vec):
    x = layers.Concatenate()([x, stn_vec])
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.1)(x)
    return layers.Dense(1, name="aqi")(x)


def build_lstm(window: int, n_feats: int, n_stations: int) -> Model:
    seq_in, stn_in = _inputs(window, n_feats)
    x = layers.LSTM(64, return_sequences=True)(seq_in)
    x = layers.Dropout(0.2)(x)
    x = layers.LSTM(32)(x)
    out = _head(x, _station_vec(stn_in, n_stations))
    return Model([seq_in, stn_in], out, name="lstm")


def build_gru(window: int, n_feats: int, n_stations: int) -> Model:
    seq_in, stn_in = _inputs(window, n_feats)
    x = layers.GRU(64, return_sequences=True)(seq_in)
    x = layers.Dropout(0.2)(x)
    x = layers.GRU(32)(x)
    out = _head(x, _station_vec(stn_in, n_stations))
    return Model([seq_in, stn_in], out, name="gru")


def build_transformer(window: int, n_feats: int, n_stations: int,
                      d_model: int = 64, n_heads: int = 4, ff_dim: int = 128,
                      n_blocks: int = 2, dropout: float = 0.15) -> Model:
    """Pre-norm time-series encoder.

    Tuning notes vs the first version (test MAE 28.5): wider (d_model 32->64,
    ff 64->128), **pre-norm** residual blocks (more stable for a small
    transformer), and **recency-aware pooling** - the last token is concatenated
    with the mean, restoring the "most recent step matters most" bias that the
    RNNs get for free and plain average-pooling washes out.
    """
    seq_in, stn_in = _inputs(window, n_feats)
    x = layers.Dense(d_model)(seq_in)
    pos = tf.range(start=0, limit=window, delta=1)
    x = x + layers.Embedding(window, d_model, name="pos_emb")(pos)
    x = layers.Dropout(dropout)(x)

    for _ in range(n_blocks):
        h = layers.LayerNormalization(epsilon=1e-6)(x)
        attn = layers.MultiHeadAttention(num_heads=n_heads,
                                         key_dim=d_model // n_heads,
                                         dropout=dropout)(h, h)
        x = x + attn                                     # pre-norm residual
        h = layers.LayerNormalization(epsilon=1e-6)(x)
        ff = layers.Dense(ff_dim, activation="gelu")(h)
        ff = layers.Dropout(dropout)(ff)
        ff = layers.Dense(d_model)(ff)
        x = x + ff

    x = layers.LayerNormalization(epsilon=1e-6)(x)
    # last-step representation via Cropping1D (serializable, unlike a Lambda)
    last = layers.Flatten()(layers.Cropping1D((window - 1, 0))(x))
    pooled = layers.Concatenate()([layers.GlobalAveragePooling1D()(x), last])
    out = _head(pooled, _station_vec(stn_in, n_stations))
    return Model([seq_in, stn_in], out, name="transformer")


BUILDERS = {"lstm": build_lstm, "gru": build_gru,
            "transformer": build_transformer}


def build(name: str, window: int, n_feats: int, n_stations: int) -> Model:
    """Reseed, then build — so each architecture's weight init is identical
    every run and independent of which models were built before it."""
    reseed(SEED)
    return BUILDERS[name](window, n_feats, n_stations)


_LR = {"lstm": 1e-3, "gru": 1e-3, "transformer": 1e-3}
_PATIENCE = {"transformer": 8}


def _optimizer(name: str, data: dict, epochs: int, batch: int):
    """Transformer: linear warmup (3 epochs) -> cosine decay to ~1/20 peak.
    RNNs: plain Adam (ReduceLROnPlateau handles their decay)."""
    peak = _LR.get(name, 1e-3)
    if name != "transformer":
        return tf.keras.optimizers.Adam(peak)
    steps = max(1, len(data["ytr"]) // batch)
    sched = tf.keras.optimizers.schedules.CosineDecay(
        initial_learning_rate=0.0, decay_steps=steps * epochs,
        warmup_target=peak, warmup_steps=steps * 3, alpha=0.05)
    return tf.keras.optimizers.Adam(sched)


def train_nn(name: str, model: Model, data: dict, ckpt_path,
             epochs: int = 30, batch: int = 256, verbose: int = 2):
    """Compile + fit with early stopping, LR scheduling and checkpointing.

    Reseeds first so dropout masks and the per-epoch shuffle are reproducible.
    """
    reseed(SEED)
    model.compile(optimizer=_optimizer(name, data, epochs, batch),
                  loss="mse", metrics=["mae"])
    cbs = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=_PATIENCE.get(name, 5),
            restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(
            str(ckpt_path), monitor="val_loss", save_best_only=True),
    ]
    if name != "transformer":                          # schedule owns the LR
        cbs.insert(1, tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.5, patience=3, min_lr=1e-5))
    hist = model.fit(
        {"seq": data["Xtr"], "station": data["Str"]}, data["ytr"],
        validation_data=(
            {"seq": data["Xva"], "station": data["Sva"]}, data["yva"]),
        epochs=epochs, batch_size=batch, callbacks=cbs, verbose=verbose,
        shuffle=True,
    )
    return hist


def predict_nn(model: Model, X: np.ndarray, S: np.ndarray) -> np.ndarray:
    return model.predict({"seq": X, "station": S}, batch_size=512,
                         verbose=0).ravel()
