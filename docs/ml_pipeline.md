# SMART AQI — ML Pipeline

Code: `backend/ml/` (`preprocessing.py`, `nn_common.py`, `lstm_model.py`,
`gru_model.py`, `transformer_model.py`, `baseline_model.py`, `evaluate.py`,
`train_models.py`). Artifacts: `backend/ml_models/`. Feature data:
`data/processed/`.

## 1. From cleaned data to features

```
data/cleaned/station_hour.csv.gz  (2.35 M rows, 110 stations, 2015–2020)
        │  aggregate hourly → station-day
        │  per (station, day): mean of every pollutant + AQI;
        │  AQI max/min/std, PM2.5/PM10 max, diurnal range, n_hours_aqi
        │  a day's AQI is dropped if < 4 valid hourly AQI values
station-day panel
        │  per-station, calendar-aware (asfreq D so gaps are real):
        │  AQI lag 1/2/3/7 · roll mean 3/7 · roll std 7 (all shift(1), no leak)
        │  dow · month · doy sin/cos · season one-hot
        │  target = next-day AQI  (shift(-1))
feature table  → data/processed/feature_table.parquet
```

**Why daily, not hourly.** The product is a 7-day *daily* forecast. Stepping an
hourly model 168 times compounds error badly and a 2 M-row deep net is
intractable on CPU. Aggregating keeps the hourly signal (daily max/min/std,
diurnal range, coverage counts) while the modelling target stays daily. This
refines the "station-hour pooled panel" decision (`docs/dataset.md` §6), it
does not abandon it.

**Weather features.** `scripts/backfill_weather.py` pulls 2015–2020 daily
weather from the Open-Meteo archive (ERA5, no key; resumable + ERA5-grid
deduplicated to respect the rate limit) into
`data/processed/weather_history.parquet` — **82 stations × 2009 days**
(`temp_mean/max/min, humidity, wind_mean/max, pressure, rain`). `preprocessing`
LEFT-joins it by `(station_id, date)`; the flat model gets all 8 as
contemporaneous features, the sequence models get `wind_mean, temp_mean, rain`
as extra channels. 94 of the 95 model stations now have real weather (after the fuzzy
geolocation pass); the 1 without keeps null weather (XGBoost handles nulls; the
NN imputes with the train median). Net effect of the weather features: a small,
stable gain for the XGBoost baseline (test MAE ~20.8 → ~20.1); the sequence
models vary run-to-run and show no consistent benefit.

## 2. Chronological split (no shuffling)

Split by the **target date**:

| Split | Target date range | Flat rows | Seq rows |
|---|---|---:|---:|
| train | ≤ 2019-06-30 | ~46 k | ~51 k |
| val | 2019-07-01 … 2019-12-31 | ~15 k | ~16 k |
| test | 2020-01-01 … 2020-07-01 | ~15 k | ~16 k |

Only stations with ≥ 250 usable target days are kept (**95 stations**).
`StandardScaler` for features, sequence channels and the target is **fit on
train only**; medians for NN imputation are train-only too. Saved to
`data/processed/scalers.joblib`.

## 3. Models

All predict next-day AQI; a single pooled model per architecture serves every
station via a **station-index embedding** (dim 8).

| Model | File | Shape |
|---|---|---|
| Baseline | `baseline_model.py` | XGBoost regressor on the 37 flat features (incl. 8 weather) + `station_idx`. Handles NaN natively. 800 trees, depth 6, lr 0.03, early stopping on val. |
| LSTM | `lstm_model.py` → `nn_common.build_lstm` | seq (21×13) → LSTM 64 (return_seq) → Dropout 0.2 → LSTM 32 → concat station-emb → Dense 32 → Dropout 0.1 → Dense 1 |
| GRU | `gru_model.py` | same as LSTM with GRU cells |
| Transformer | `transformer_model.py` → `nn_common.build_transformer` | Dense→d_model **64** + learned positional embedding + dropout → 2× **pre-norm** blocks (LayerNorm→MHA 4 heads→+residual ; LayerNorm→FFN **128** GELU→+residual) → LayerNorm → **concat[mean-pool, last-step]** → concat station-emb → Dense 32 → Dense 1. ~73k params. |

Sequence input channels (21 daily steps): `AQI, PM25, PM10, NO2, SO2, CO, O3,
wind_mean, temp_mean, rain, doy_sin, doy_cos, dow`.

Training (`nn_common.train_nn`): Adam, MSE loss, batch 256, up to 40 epochs,
**EarlyStopping** (patience 5; **8** for the Transformer, restore-best) +
**ModelCheckpoint** (best val_loss). LSTM/GRU: constant LR 1e-3 +
**ReduceLROnPlateau** (×0.5, patience 3). **Transformer: 3-epoch linear warmup
to 1e-3 then CosineDecay** (schedule owns the LR, so no ReduceLROnPlateau).

## 4. Evaluation & selection

`evaluate.regression_metrics` on the **inverse-scaled** test predictions:
MAE, RMSE, R², MAPE (denominator floored at 20 AQI so near-zero days don't
distort the percentage). Reported on the real AQI scale.

### Reproducibility

`backend/ml/nn_common.py` sets `PYTHONHASHSEED`, seeds Python / NumPy /
TensorFlow via `tf.keras.utils.set_random_seed(ML_SEED)` (default 42), and calls
`tf.config.experimental.enable_op_determinism()`. Every model is re-seeded
immediately before it is **built** and again before **fit**, so each
architecture's result is identical run-to-run and independent of the order the
models were trained in. Verified: two independent training runs produced
bit-identical test MAE for all four models. Op-determinism roughly doubles NN
training time — an accepted cost. XGBoost already uses `random_state=42`.

Seeded reference numbers (40 epochs, 94-station weather):
`baseline` MAE **20.14** R² 0.895 (best) · `gru` 22.82 · `lstm` 23.72 ·
`transformer` **23.62** R² 0.870. After tuning (pre-norm, wider, recency-aware
pooling, LR warmup) the Transformer went 28.48 → **23.62** and now sits with
the RNNs. `scripts/tune_transformer.py` iterates on it alone.

The best model is the one with the lowest **validation** MAE — computed at
runtime, written as `is_best` in `model_metrics.json` and the `model_metrics`
collection. Never hard-coded.

## 5. Outputs

```
backend/ml_models/
  baseline_model.joblib     lstm_model.keras   gru_model.keras
  transformer_model.keras   scalers.joblib     feature_config.json
  model_metrics.json        # full comparison + best_model + resid_std_best
data/processed/
  feature_table.parquet     seq_train.npz  seq_val.npz  seq_test.npz
  scalers.joblib            feature_config.json
```

MongoDB: `model_metrics` (one row per model per run, `is_best` flag);
`forecast_records` (sample recursive 7-day forecasts — see `docs/forecasting.md`).

## 6. Run

```bash
python -m backend.ml.preprocessing              # (re)build feature data
python -m backend.ml.train_models --epochs 40   # train + evaluate + seed
python -m backend.ml.train_models --rebuild --no-seed --epochs 40
```
