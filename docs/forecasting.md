# SMART AQI — 7-Day Forecasting Methodology

## Approach

Recursive multi-step forecasting with the **best** model (selected by
validation MAE). Starting from a station's most recent observed window, predict
day +1, append that prediction to the input, advance the calendar, predict
day +2, and so on to day +7.

- **Baseline (XGBoost):** each future day's flat feature vector is rebuilt from
  the growing AQI history — lags 1/2/3/7 and rolling mean/std use predicted
  values once they run past the last observation.
- **Sequence models (LSTM / GRU / Transformer):** the 21-day input buffer is
  rolled forward one day at a time; the predicted AQI becomes the new `AQI`
  channel value, `doy_sin`/`doy_cos`/`dow` advance for real.

## Documented limitations

- **Pollutant channels are persisted** at their last observed daily value
  through the horizon. A fuller system would couple a pollutant forecast (or
  pull Open-Meteo's air-quality forecast); until then this is the honest,
  clearly-labelled simplification. It mainly matters for the sequence models,
  whose PM2.5/PM10/… channels stop being informative after day 1.
- Forecasts are only generated for stations with at least `SEQ_WINDOW + 3` days
  of usable recent history. A station without that returns
  `forecast_available: false` — never a fabricated series.
- Every stored forecast row carries `is_prediction: true` and a `method`
  string. The UI must always label these as predictions, never measurements.

## Uncertainty band

Approximate. From the best model's one-step test residual standard deviation
`σ`, the day-`h` band is `± 1.2816 · σ · √h` (≈ 80 % if residuals were
Gaussian and independent — they are neither exactly, hence "approximate"). The
band widens with horizon. Stored as `lower` / `upper` (clipped at 0).

## AQI categories

`predicted_AQI` is mapped to a CPCB category with
`backend/config/aqi_categories.py` (`categorize()`), the same table used
everywhere else. Values above the 500 scale cap keep their raw number for
modelling but display as "500+".

## Storage — `forecast_records`

`_id = "<station_id>:<model>:<YYYY-MM-DD>:<horizon_day>"`
```jsonc
{
  "level": "station", "state": "...", "city": "...", "district": null,
  "station_id": "DL008",
  "model": "baseline", "generated_at": ISO, "horizon_day": 3,
  "forecast_date": "2020-07-04",
  "predicted_AQI": 148.2, "AQI_bucket": "Moderate",
  "lower": 119.0, "upper": 177.4,
  "is_prediction": true,
  "method": "recursive multi-step; pollutant channels persisted"
}
```

## Coverage

`backend/ml/forecast.py` is the canonical recursive-forecast path (used by both
the training run and the standalone script). `scripts/generate_forecasts.py`
forecasts **every** station in `feature_table.parquet` with at least
`SEQ_WINDOW + 3` days of usable recent history and upserts the rows.

Current run: **95 stations · 665 rows · 22 cities across 19 states**, model
`baseline`. Deterministic `_id` (`<sid>:<model>:<YYYY-MM-DD>:<h>`) means it is
idempotent. Stations without enough history (e.g. Aizawl, which starts in 2020)
correctly get `forecast_available: false` from the API — never a fabricated
series.

## Regenerate

```bash
python -m backend.ml.train_models --epochs 40   # retrain, reseeds a sample
python scripts/generate_forecasts.py            # full coverage, all eligible stations
python scripts/generate_forecasts.py --limit 5  # smoke
```
