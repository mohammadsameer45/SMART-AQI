# SMART AQI

[![CI](https://github.com/mohammadsameer45/SMART-AQI/actions/workflows/ci.yml/badge.svg)](https://github.com/mohammadsameer45/SMART-AQI/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![React 19 + Vite](https://img.shields.io/badge/react-19%20%2B%20vite-149eca)
![tests](https://img.shields.io/badge/tests-30%20backend%20%2B%2012%20frontend-brightgreen)

An intelligent air-quality monitoring, visualisation, **7-day forecasting** and
health-advisory platform for **India → State → District/City → Station**.

Premium dark React (Vite) frontend with real Three.js visualisations · Flask
REST API · MongoDB · a four-model ML engine (XGBoost / LSTM / GRU / Transformer)
selected automatically by validation error.

> **Data honesty is the first rule.** No fabricated AQI, districts, weather or
> forecasts. Where a source genuinely lacks data it is `null` and the UI says
> so — it never shows an invented value or a broken "N/A" card.

---

## Architecture

```
React 18 + Vite  (SPA, React Router, Axios, Three.js/R3F/drei, Framer Motion, Recharts)
        │  /api  (JWT bearer, {ok,data|error} envelope)
Flask REST API   (Flask-CORS, blueprints → services → models)
        │
MongoDB (local, "smart_aqi")        backend/ml_models/  (.keras, .joblib, metrics)

Offline pipelines (scripts/, backend/ml/):
  audit → clean → validate → (boundaries) → seed_database
  preprocessing → train_models (baseline + LSTM + GRU + Transformer) → export_insights
```

Full detail: [`docs/architecture.md`](docs/architecture.md).

## Technology

| Area | Stack |
|---|---|
| Frontend | React 19 (pinned 19.2 for R3F), **Vite**, React Router, Axios, Three.js, @react-three/fiber, @react-three/drei, Framer Motion, GSAP, Recharts. Hand-written CSS, **no Tailwind**. |
| Backend | Python 3.11, Flask, Flask-CORS, PyMongo, PyJWT, bcrypt |
| Database | MongoDB (local, inspected with MongoDB Compass) |
| ML | pandas, numpy, scikit-learn, **TensorFlow/Keras**, XGBoost, joblib, pyarrow |
| Data | Kaggle *Air Quality Data in India 2015–2020* (CPCB), geoBoundaries ADM1/ADM2, data.gov.in CPCB live, Open-Meteo weather (current + ERA5 archive) |

## Folder structure

```
AQI PROJECT/
├── data/            raw/ cleaned/ processed/ validation/ metadata/
├── scripts/         audit_raw_data · clean_data · validate_data · seed_database · smoke_api
├── backend/
│   ├── app.py  config/  routes/  services/  models/  ml/  utils/  tests/
│   └── ml_models/   trained artifacts + model_metrics.json
├── frontend/        Vite React app (src/ api auth components layouts three charts hooks pages styles)
└── docs/            architecture · dataset · mongodb · ml_pipeline · forecasting · api · ui_design · health_advisory
```

---

## Prerequisites

- Python 3.11, Node 20+, a local **MongoDB** server on `mongodb://localhost:27017`
- The Kaggle dataset zip at `C:\Users\new\Desktop\archive.zip` (already present in this environment)

## Setup

### 1. Backend deps

```bash
python -m pip install -r backend/requirements.txt
# NOTE (Windows): TensorFlow must import before XGBoost — backend/ml/__init__.py
# enforces this; keep it.
```

### 2. Environment

```bash
cp backend/.env.example backend/.env
# a generated JWT_SECRET is already filled in this environment.
python -c "import secrets; print(secrets.token_urlsafe(48))"   # to regenerate
```

`backend/.env` keys: `MONGO_URI`, `MONGO_DB`, `JWT_SECRET`, `FRONTEND_URL`,
`DATA_GOV_IN_API_KEY` (optional, enables the live feed + weather),
`OPEN_METEO_BASE`.

### 3. Data pipeline

```bash
python scripts/audit_raw_data.py     # profile the raw CSVs        -> data/validation/raw_audit.*
python scripts/clean_data.py         # canonicalise + clean        -> data/cleaned/*.csv.gz
python scripts/validate_data.py      # automated checks (all PASS)  -> data/validation/validation_report.*
```

Boundaries (geoBoundaries ADM1 + ADM2) are already fetched into `data/metadata/`.

### 3b. Live CPCB layer + district join (needs `DATA_GOV_IN_API_KEY`)

```bash
python scripts/ingest_cpcb_live.py        # ~500 live stations -> cpcb_live + aqi_records, writes station coords
python scripts/geolocate_stations.py --apply   # fuzzy-match stations the feed re-labelled -> +coords
python scripts/build_station_districts.py # point-in-polygon coords -> real districts (needs shapely)

# keep it current — run as its own long-lived process:
python scripts/refresh_worker.py            # loop, re-pull every LIVE_REFRESH_MINUTES (45)
python scripts/refresh_worker.py --once     # single cycle (for Windows Task Scheduler / cron)
```

### 4. Seed MongoDB

```bash
python scripts/seed_database.py            # idempotent
python scripts/seed_database.py --drop     # rebuild from scratch
```

Seeds `locations` (136), `aqi_records` (129,305 daily), `health_advisories` (12);
creates `forecast_records` / `model_metrics` / `users` with indexes.
Inspect in **MongoDB Compass** → database `smart_aqi`.

### 5. Train models

```bash
python -m backend.ml.preprocessing        # feature data -> data/processed/
python -m backend.ml.train_models --epochs 40
python -m backend.ml.export_insights      # actual-vs-predicted samples
python scripts/generate_forecasts.py      # 7-day forecasts for every eligible station
```

Writes `backend/ml_models/` and seeds `model_metrics` + `forecast_records`
(95 stations · 665 rows).

### 6. Run

```bash
# terminal 1 — API
python -m backend.app                      #  http://localhost:5000

# terminal 2 — frontend
cd frontend && npm install && npm run dev   #  http://localhost:5173  (proxies /api)
```

Open **http://localhost:5173**, create an account, pick a state + city, explore.

---

## Verify

```bash
python scripts/smoke_api.py            # 18-check end-to-end API smoke
python -m pytest backend/tests -q      # backend + ML unit/integration tests (26)
cd frontend && npm run build           # frontend compiles (1645 modules)
cd frontend && npm test                # frontend unit tests (vitest, 12)
```

## API

Base `http://localhost:5000/api`, JWT bearer, `{ok,data|error}` envelope.
Endpoints: `auth/{register,login,me}`, `states`, `states/:s/districts`,
`districts/:s/:a/locations`, `aqi/{current,history,forecast}/:s/:a`,
`pollutants/:s/:a`, `health-advisory/:s/:a`, `model-metrics`,
`model-insights/:model`, `dashboard/:s/:a`. Full table:
[`docs/api.md`](docs/api.md).

## ML methodology (summary)

- Hourly station panel (2.35 M rows) → **station-day** aggregation with rich
  daily features (max/min/std, diurnal range, coverage counts).
- Features: AQI lags 1/2/3/7, rolling mean/std, calendar (dow, month, doy
  sin/cos, season), pollutant levels, **daily weather** (temp/humidity/wind/
  pressure/rain, Open-Meteo ERA5, 82 geolocated stations), station embedding.
- **Chronological split** (train ≤ 2019-06-30 · val H2-2019 · test H1-2020),
  scalers fit on train only, no shuffling.
- Models: XGBoost baseline, 2-layer LSTM, 2-layer GRU, time-series Transformer
  (learned positional embedding + multi-head attention + FFN + LayerNorm).
- **Best model chosen by validation MAE** — written as `is_best`, never
  hard-coded. Weather features (Open-Meteo archive, 82 geolocated stations)
  were added and the models retrained (94 geolocated stations get real
  weather, the rest imputed). The tree **baseline** gained a small, stable
  improvement — test MAE **20.82 → 20.14**, R² **0.886 → 0.895**; it stays the
  best model. Training is now deterministic (fixed `ML_SEED`). The sequence models are now **seed-stabilised**
  (`enable_op_determinism` + `set_random_seed(ML_SEED)`, verified bit-identical
  across runs): GRU **22.8**, LSTM **23.7**, Transformer **23.6** (R² 0.87) —
  the Transformer was tuned (pre-norm blocks, wider, recency-aware pooling, LR
  warmup→cosine) from 28.5 down into the RNN band.
- 7-day forecast: recursive multi-step, pollutant channels persisted (documented
  limitation), ±80 % band from residual spread that widens with horizon.

Detail: [`docs/ml_pipeline.md`](docs/ml_pipeline.md),
[`docs/forecasting.md`](docs/forecasting.md).

## Health advisory

CPCB six-category thresholds (single source of truth in
`backend/config/aqi_categories.py`). Advisory content
(`backend/config/health_advisories_seed.py`) is derived from CPCB health-impact
statements plus standard precautionary guidance, per audience
(`general`, `sensitive`), and blended with the forecast for tomorrow / 7-day
outlook. **Informational decision-support only — not a diagnosis, never a
medication instruction.** Detail: [`docs/health_advisory.md`](docs/health_advisory.md).

## Current limitations

- **Live current AQI** comes from the CPCB CAAQMS feed and is *computed* with
  the CPCB sub-index method from spot `avg_value` readings (not 24 h/8 h
  rolling averages), so it approximates — not reproduces — the official portal
  value. `is_live:false` falls back to the latest 2020 historical value with a
  clear note. Run `scripts/ingest_cpcb_live.py` periodically to refresh.
- **Districts** exist for **93** historical stations — exact + fuzzy name-match
  to a current CPCB station gives coordinates, then point-in-polygon on
  geoBoundaries ADM2. 16 stations absent from the current feed, plus the pure
  city-level series, stay at city granularity. District names use
  geoBoundaries' spellings.
- 7-day forecasts cover the 95 stations with enough history; others return
  `forecast_available:false`.
- **Weather** (Open-Meteo, no key) is live for areas with a geolocated station;
  it uses that station's coordinates and reports `available:false` elsewhere.
  ML models do not yet use weather features (historical backfill + retrain is a
  follow-up).

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ImportError: DLL … _pywrap_tensorflow` | XGBoost imported before TensorFlow. Keep `backend/ml/__init__.py`; import `backend.ml.*` before `xgboost`. |
| `RuntimeError: Missing … JWT_SECRET` | `backend/.env` missing/empty — copy from `.env.example` and fill. |
| API 500s / `mongo_ok:false` at `/api/health` | local MongoDB not running. |
| Frontend can't reach API | run the Flask app first; Vite proxies `/api` → `:5000`. Vite binds `localhost` (IPv6) — use `http://localhost:5173`, not `127.0.0.1`. |
| `@react-three/fiber` peer error on install | React is pinned to `19.2.0` in `frontend/package.json`; keep the exact pin. |
| Empty dashboards | run the data pipeline + `seed_database.py`; check Compass shows `smart_aqi`. |

## Attribution / licence of data

Air-quality data © CPCB, via the Kaggle "Air Quality Data in India (2015–2020)"
release. Administrative boundaries © geoBoundaries (CC-BY 4.0). This project is
for educational/analytical use and is **not medical advice**.
