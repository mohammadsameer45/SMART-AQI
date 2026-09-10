# SMART AQI — MongoDB

Local server, database **`smart_aqi`**. Inspect with MongoDB Compass at
`mongodb://localhost:27017`.

Built by `scripts/seed_database.py` from the cleaned **daily** tables
(`data/cleaned/city_day.csv.gz`, `station_day.csv.gz`). Hourly data is *not*
loaded — it stays in `data/cleaned/` for the ML pipeline.

## Seeded state (Phase 6)

| Collection | Docs | Notes |
|---|---:|---|
| `locations` | 136 | 26 city + 110 station monitoring locations |
| `aqi_records` | 129,305 | 28,157 city-day + 101,148 station-day observations |
| `health_advisories` | 12 | 6 CPCB categories × {general, sensitive} baseline |
| `forecast_records` | 0 | filled by `backend/ml/train_models.py` (Phase 10) |
| `model_metrics` | 0 | filled by training (Phase 8) |
| `users` | 0 | created on registration (Phase 12) |

States present: 21. `district` is `null` on every record until the
station→district spatial join runs (needs `shapely` + CPCB station coordinates).

## Document shapes

### `locations`  — `_id = "city:<state>|<city>"` or `"station:<StationId>"`
```jsonc
{
  "_id": "station:DL008",
  "level": "station",                 // "city" | "station"
  "state": "Delhi", "city": "Delhi", "district": null,
  "station": "DTU, Delhi - CPCB", "station_id": "DL008",
  "lat": null, "lon": null,           // filled by CPCB coords later
  "grains": ["day"],                  // grains present in aqi_records
  "grains_available": ["day", "hour"],// grains present in data/cleaned/
  "sources": ["station_day"],
  "has_history": true,
  "history_start": "2015-01-01", "history_end": "2020-07-01",
  "n_records": 1417,
  "updated_at": ISODate
}
```

### `aqi_records`  — `_id = "<source>:<station_id|city>:<date>"`
```jsonc
{
  "_id": "station_day:DL008:2020-07-01",
  "level": "station",
  "state": "Delhi", "city": "Delhi", "district": null,
  "station": "DTU, Delhi - CPCB", "station_id": "DL008",
  "date": "2020-07-01", "ts": ISODate("2020-07-01T00:00:00Z"),
  "grain": "day", "year": 2020, "month": 7,
  "PM25": 54.01, "PM10": 128.66, "NO": null, "NO2": 21.05, "NOx": null,
  "NH3": null, "CO": 0.68, "SO2": 9.2, "O3": 38.4,
  "Benzene": null, "Toluene": null, "Xylene": null,
  "AQI": 101.0,               // raw, may exceed 500 during severe episodes
  "AQI_display": 101.0,       // min(AQI, 500) for the UI
  "AQI_bucket": "Moderate",   // CPCB label, validated consistent with AQI
  "source": "station_day", "ingested_at": "2026-09-10T..."
}
```
Missing measurements are `null` — never imputed.

### `health_advisories`  — `_id = "<AQI_bucket>:<audience>"`
```jsonc
{
  "_id": "Poor:sensitive",
  "aqi_bucket": "Poor", "audience": "sensitive", "severity": 3,
  "headline": "Sensitive groups: avoid prolonged outdoor exertion.",
  "outdoor_activity": "Avoid prolonged or heavy outdoor exertion; ...",
  "guidance": ["People with asthma, respiratory or heart conditions ...", "..."],
  "disclaimer": "General precautionary guidance only. SMART AQI does not ...",
  "source": "CPCB National Air Quality Index health-impact statements + ...",
  "updated_at": ISODate
}
```

### `forecast_records` (shape, not yet populated)
`_id` per `(station_id|city, model, generated_at, horizon_day)`; fields
`state, city, district, station_id, model, generated_at, horizon_day (1..7),
forecast_date, predicted_AQI, AQI_bucket, lower, upper, is_prediction: true`.

### `model_metrics` (shape, not yet populated)
`_id = "<model_name>:<training_date>"`; fields `model_name, MAE, RMSE, R2,
MAPE, training_time_s, n_train, n_val, n_test, split, is_best, training_date,
feature_importance?`.

### `users`
`{ _id, name, email (unique, lowercased), password_hash (bcrypt), created_at }`

## Indexes

| Collection | Index | Purpose |
|---|---|---|
| `users` | `ux_email` (unique), `ix_created` | login, listing |
| `locations` | `ix_state`, `ix_state_district`, `ix_state_district_city`, `ix_state_city`, `ux_station_id` (unique, partial on string), `ix_level` | selector population |
| `aqi_records` | `ix_state_district_ts`, `ix_state_city_ts`, `ix_station_ts` (partial on string), `ix_level_ts`, `ix_ts` | history / latest / range queries |
| `forecast_records` | `ix_state_city_generated`, `ix_station_forecastdate`, `ix_model_generated` | forecast retrieval |
| `model_metrics` | `ix_model`, `ix_trained`, `ix_is_best` | model insights |
| `health_advisories` | `ux_bucket_audience` (unique) | advisory lookup |

## Running it

```bash
python scripts/seed_database.py            # idempotent upsert of everything
python scripts/seed_database.py --drop     # drop smart_aqi collections first
python scripts/seed_database.py --only locations,aqi_records
```

Every document has a deterministic `_id`, so re-running never creates
duplicates (an unchanged re-seed reports `0` changed).
