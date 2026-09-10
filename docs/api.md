# SMART AQI — REST API

Base URL `http://localhost:5000/api`. JSON only.

**Envelope** — every response:
```jsonc
{ "ok": true,  "data": ... }
{ "ok": false, "error": { "code": "string", "message": "string", ... } }
```

**Auth** — all endpoints except `/health`, `/auth/register`, `/auth/login`
require `Authorization: Bearer <jwt>`. Missing/expired/invalid → `401`.

**Area path segment** — `:area` is matched against `district` first, then the
monitoring `city`. Until the station→district spatial join runs, districts are
`null`, so in practice `:area` is a city name and `/states/:state/districts`
returns `{"level": "city", ...}`.

| Method & path | Auth | Purpose |
|---|:--:|---|
| `GET /health` | – | service + MongoDB status |
| `POST /auth/register` | – | `{name,email,password,confirm_password}` → `{token,user}` (201). Validates email, name, password strength (≥8, ≥3 char classes), match. `409` if email taken. |
| `POST /auth/login` | – | `{email,password}` → `{token,user}`. `401` on bad creds. |
| `GET /auth/me` | ✔ | current user |
| `GET /states` | ✔ | `["Delhi", ...]` — 21 states with data |
| `GET /states/:state/districts` | ✔ | `{level:"district"\|"city", items:[...]}`. `404` unknown state. |
| `GET /states/:state/overview` | ✓ | `{avg_aqi, avg_bucket, current, n_districts, n_cities, n_stations, records, coverage, distribution[6], monthly_trend[], districts[], best_districts[5], worst_districts[5]}`. `404` unknown state. Cached 5 min. |
| `GET /districts/:state/:area/locations` | ✔ | `{matched_level, locations:[...], coverage}` — the monitoring stations/cities under an area |
| `GET /aqi/current/:state/:area` | ✔ | latest value: `{available, as_of, is_live, AQI, AQI_display, AQI_bucket, category, pollutants, stations[]}`. `is_live:true` + `source_note` "Live CPCB reading via data.gov.in (computed AQI …)" when a station in the area reported in the last 6 h; otherwise `is_live:false` and the note points at the 2020 historical value. |
| `GET /aqi/history/:state/:area?from=&to=&grain=day` | ✔ | `{count, series:[{date,AQI,AQI_display,AQI_bucket,PM25,...}]}` (`from`/`to` = `YYYY-MM-DD`) |
| `GET /aqi/forecast/:state/:area?model=` | ✔ | `{forecast_available, model, generated_at, is_prediction:true, days:[{horizon_day,forecast_date,predicted_AQI,AQI_bucket,lower,upper}]}`. When history is insufficient: `{forecast_available:false, reason}`. |
| `GET /pollutants/:state/:area` | ✔ | per-pollutant `{current, unit, trend_mean/min/max, n, health_relevance}` for PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3 |
| `GET /health-advisory/:state/:area` | ✔ | `{current_AQI, current_bucket, severity, air_quality_status, who_should_take_care[], outdoor_activity, respiratory_precautions[], cards:{general,sensitive}, tomorrow_risk, seven_day_outlook, disclaimer}` |
| `GET /model-metrics` | ✔ | `{models:[{model_name,MAE,RMSE,R2,MAPE,val_MAE,training_time_s,is_best}], best_model, selection_metric}` |
| `GET /model-insights/:model` | ✔ | `{metrics, split, feature_importance, actual_vs_predicted:[{actual,predicted}], error_hist}`. `model` ∈ baseline\|lstm\|gru\|transformer. |
| `GET /map/india` | ✓ | slim GeoJSON of the 36 states, simplified + rounded (~300 KB), each feature tagged `{aqi, aqi_bucket, n_stations, has_data, source}` from live CPCB (else latest historical). Cached 5 min. |
| `GET /map/state/:state` | ✓ | slim ADM2 GeoJSON for that state's districts that have data, each with `{aqi, aqi_bucket, has_data}`. |
| `GET /weather/:state/:area` | ✔ | Open-Meteo (no key): `{available, source, as_of, location:{lat,lon,reference_station}, current:{temperature,humidity,wind_speed,pressure,rainfall,condition}, units, daily:[{date,t_max,t_min,rain_mm,wind_max_ms,condition}]×7}`. `{available:false, reason}` when the area has no geolocated station — no location is guessed. |
| `GET /live/status` | ✓ | freshness of the scheduled CPCB refresh (`scripts/refresh_worker.py`): `{available, age_minutes, ok, ingest, district_join, cpcb_live_stations, cpcb_live_with_aqi}` or `{available:false, reason}` if the worker has never run. |
| `GET /dashboard/:state/:area` | ✔ | composite: `{coverage, current, history_90d, forecast, advisory, weather, live_refresh}` in one call |

## Architecture

```
backend/
  app.py            application factory, CORS locked to FRONTEND_URL,
                    {ok,data|error} handlers for ApiError / HTTPException / 500
  config/           settings, aqi_categories, health_advisories_seed
  routes/           auth_ location_ aqi_ forecast_ health_ model_routes.py (blueprints)
  services/         auth_ location_ aqi_ forecast_ health_ model_service.py
  models/           mongo_models.py  (client, collections, indexes, DAOs)
  utils/            auth.py (JWT+bcrypt+@require_auth), validation.py, responses.py
```

## Run

```bash
# .env is created with a generated JWT_SECRET; MongoDB must be seeded
python -m backend.app                       # dev server on 127.0.0.1:5000
python scripts/smoke_api.py                 # 18-check end-to-end smoke test
python -m pytest backend/tests -q           # unit + integration tests
```

## Notes / current limitations

- `is_live:true` when a CPCB station in the area reported in the last 6 h
  (`DATA_GOV_IN_API_KEY` configured); otherwise `false` with the 2020 fallback.
  The live AQI is *computed* (CPCB sub-index method) from spot readings.
- `/aqi/forecast` covers the 95 stations with sufficient history; others return
  `forecast_available:false`.
- `/weather` and district resolution work for the 82 stations whose 2020 names
  matched a current CPCB station (→ coordinates). Others stay at city level.
