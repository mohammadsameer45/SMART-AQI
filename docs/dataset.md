# SMART AQI — Dataset Audit & Strategy

_Phase 3 deliverable. Machine-readable profile: `data/validation/raw_audit.json`.
Full per-file tables: `data/validation/raw_audit.md`. This document interprets
those results and defines the data strategy._

---

## 1. What the supplied ZIP actually contains

`C:\Users\new\Desktop\archive.zip` → **Kaggle "Air Quality Data in India
(2015–2020)"**. Five CSVs, ~283 MB unzipped, extracted to `data/raw/`.

| File | Rows | Grain | Date range | Geo keys |
|---|---:|---|---|---|
| `stations.csv` | 229 | station master | — | StationId, StationName, City, State, Status |
| `city_day.csv` | 29,531 | city × day | 2015-01-01 → 2020-07-01 | City |
| `city_hour.csv` | 707,875 | city × hour | 2015-01-01 → 2020-07-01 | City |
| `station_day.csv` | 108,035 | station × day | 2015-01-01 → 2020-07-01 | StationId |
| `station_hour.csv` | 2,589,083 | station × hour | 2015-01-01 → 2020-07-01 | StationId |

Pollutant columns (all files): `PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3,
Benzene, Toluene, Xylene`, plus `AQI` and `AQI_Bucket`.

### Findings

- **No district column anywhere.** Hierarchy present is **State → City →
  Station** only. `stations.csv` has no coordinates either.
- **No weather columns anywhere.** No temperature, humidity, wind, pressure or
  rainfall. Weather must come from Open-Meteo or be omitted.
- **`city_day.csv` has no `State` column** — state is recovered by joining
  `City` → `stations.csv`. All 26 cities join cleanly to 17 states.
- **`AQI_Bucket` already matches the CPCB 6-category scale exactly** — 0
  mismatches against `Good / Satisfactory / Moderate / Poor / Very Poor /
  Severe` thresholds across ~2.7 M rows. We adopt these thresholds verbatim.
- **Data ends 2020-07-01.** "Current AQI" cannot come from this dataset.
- **Missingness is real and substantial.** Daily files: AQI ~16–22 % null;
  `PM10` ~38–43 % null; `Xylene` 61–80 % null; `NH3` ~35–48 % null. No negative
  pollutant values. A small number of implausible highs (e.g. `AQI` up to
  2049/3133; `CO` > 50 mg/m³ on ~120–2 978 rows) — flagged for capping in
  cleaning, **not** deletion unless clearly corrupt.
- Placeholder tokens: the only textual placeholder is `NaN`/empty in
  `AQI_Bucket` (mirrors null `AQI`). No `"Not Found"` / `"N/A"` strings.
- **Duplicates:** 0 on the natural key of every file.
- Station status: of 229, only 131 `Active`, 2 `Inactive`, 96 blank.

---

## 2. Time-series depth — how many places can actually be forecast

7-day forecasting with LSTM/GRU/Transformer needs multi-year, mostly-complete
daily history. From `city_day.csv`:

| History available | Cities |
|---|---|
| ≥ 3.5 yr daily, ≥ 75 % AQI coverage | **8** — Delhi, Lucknow, Bengaluru, Chennai, Hyderabad, Patna, Gurugram, Visakhapatnam |
| ≥ 2 yr daily | ~15 |
| < 1 yr (starts 2019–2020) | Aizawl, Kochi, Ernakulam, Bhopal, Chandigarh, Shillong, Coimbatore, Guwahati … |

`station_day.csv` (110 stations, same 2015–2020 window) widens this to ~40–60
station-level series with ≥ 2 yr history; `station_hour.csv` (2.6 M rows) gives
the density deep-learning models prefer.

**Consequence:** genuine forecasts are possible for roughly **20–50 monitoring
locations**, not for hundreds of districts. This is a property of the data, not
a bug to code around. The application must expose forecasts only where history
supports them and say so plainly everywhere else — never a fabricated series.

---

## 3. The three data layers and how they reconcile

| Layer | Source | Gives us | Does **not** give us |
|---|---|---|---|
| **A. Historical panel** | Kaggle CSVs (this ZIP) | 2015–2020 daily & hourly AQI + 12 pollutants for 26 cities / 110 stations across 21 states. Training data for all ML. | Districts, weather, anything after 2020-07-01. |
| **B. Live snapshot** | **data.gov.in CPCB** resource `3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69` | Current AQI + PM2.5/PM10/NO2/SO2/CO/O3 for ~hundreds of stations nationwide, each with **latitude/longitude**, `city`, `station`, `last_update`. Breadth for "current AQI", pollutant snapshot, health advisory. | History (real-time only), districts (no district field), long-range forecasting. |
| **C. Weather** | **Open-Meteo** (no key) | temperature, humidity, wind speed, pressure, rainfall — historical (archive API) and forecast — by lat/long. Optional ML feature; powers weather UI. | Air quality ground truth. |
| **D. Boundaries** | **geoBoundaries / DataMeet** India ADM1 (state) + ADM2 (district) GeoJSON | Real polygons to (a) derive a **district** label for any station by point-in-polygon on its lat/long, (b) draw the map. | Measurements. |

### Deriving "district" without fabrication

Neither Kaggle nor the CPCB API carries a district field. A **real** district
label is obtained by a spatial join: take a station's actual `(lat, lon)` (from
the CPCB live resource; matched to Kaggle stations by station-name) and locate
which real ADM2 polygon contains it. That is a geometric fact about a real
coordinate, not an invented value. Stations we cannot geolocate get
`district: null` and are shown at city level only.

---

## 4. Canonical record schema (post-cleaning)

```jsonc
{
  "state":     "Delhi",          // standardised ADM1 name
  "district":  "New Delhi",      // ADM2 via spatial join, or null
  "city":      "Delhi",          // monitoring city as labelled by source
  "station":   "ITO, Delhi - CPCB",  // or null for city-grain rows
  "station_id":"DL008",          // Kaggle id where applicable, else null
  "lat": 28.6285, "lon": 77.2410,   // or null
  "date":      "2020-06-30T00:00:00Z",
  "grain":     "day",            // "day" | "hour"
  "AQI": 179, "AQI_bucket": "Moderate",
  "PM25": 71.2, "PM10": 143.0, "NO2": 34.1, "SO2": 12.0, "CO": 1.4, "O3": 38.2,
  "NO": null, "NOx": null, "NH3": null,
  "Benzene": null, "Toluene": null, "Xylene": null,
  "temperature": null, "humidity": null, "wind_speed": null,
  "pressure": null, "rainfall": null,   // filled only from Open-Meteo
  "source":    "kaggle_city_day",       // provenance on every row
  "ingested_at": "2026-09-10T…Z"
}
```

Every row carries `source`. Missing measurements stay `null` — never
interpolated into the stored record (imputation, if any, happens only inside the
ML feature pipeline and is documented there).

---

## 5. Cleaning rules (to be implemented in `scripts/clean_data.py`)

1. Standardise column names to the canonical schema.
2. Standardise state names against the ADM1 list; trim/casefold city & station.
3. Recover `State` for `city_day`/`city_hour` via `stations.csv`.
4. Parse `Date`/`Datetime` to UTC; drop rows with unparseable or future dates
   (audit found 0 of each).
5. Coerce all pollutant columns to numeric; non-numeric → null.
6. Drop rows where **every** measurement (all pollutants + AQI) is null.
7. Cap physically implausible values at documented thresholds
   (`data/validation/` records how many rows are affected); flag, don't silently
   delete, unless the whole row is corrupt.
8. De-duplicate on `(source, station_id|city, date, grain)`.
9. Keep `AQI_Bucket` from source where present; else derive from the CPCB
   threshold table in `backend/config/aqi_categories.py`.
10. Write `data/cleaned/` (parquet) + refreshed `data/validation/` quality
    report (totals, per-state, per-district, per-city counts, missing %, dupes
    removed, rows capped, pollutant stats).

---

## 6. Decisions — LOCKED 2026-09-10

1. **Grain for ML:** **station-hour pooled panel** — one model per architecture
   across all 110 stations, with station/location features.
2. **Geography in the UI:** **real district via spatial join** of station
   `(lat, lon)` to geoBoundaries ADM2. Districts without a station are simply
   absent from the picker. No-fabrication rule holds.
3. **Ingestion:** the `docs/architecture.md` §12 table is **approved in full**
   (geoBoundaries, Open-Meteo backfill, CPCB live pulls once the key is ready).

## 9. Live layer & district join — DONE 2026-09-10

The data.gov.in key is configured. `scripts/ingest_cpcb_live.py` pulls the CPCB
CAAQMS feed (**~500 stations**, all geolocated, computed AQI via the CPCB
sub-index method in `backend/config/aqi_breakpoints.py`). `cpcb_live` collection
+ `grain:"live"` rows in `aqi_records`.

Historical stations get coordinates in two passes: exact name-match to a live
station (**82**), then `scripts/geolocate_stations.py` fuzzy-matches the rest
(normalise, drop the agency suffix, difflib ratio + token overlap ≥ 0.83) to
recover stations the current feed re-labelled by operator (IMD→IITM, APCB→PCBA,
etc.) — **+12 more, 94 total**. 16 stations genuinely absent from the current
feed keep no coordinates (discontinued/renamed since 2020).

`scripts/build_station_districts.py` then point-in-polygons those 94 against
geoBoundaries ADM2/ADM1: **93/94 placed, 39 districts, 21 states**. One border
station (Aya Nagar, on the Delhi–Haryana line) whose coordinate falls in the
wrong state against the simplified polygon is left district-less rather than
mis-placed. District names carry geoBoundaries' spellings ("Ahmadabad",
"Gurgaon", "Bangalore").

Known: the CPCB feed reports CO in µg/m³ while the CPCB AQI CO sub-index is
defined in mg/m³; the client converts (÷1000) so CO stops spuriously forcing
every station to "Severe". `avg_value` is a spot reading, not a rolling
average, so the live AQI is labelled "computed", not the official portal value.

---

## 7. Cleaning results (Phase 4–5, `scripts/clean_data.py` + `validate_data.py`)

Cleaned tables written to `data/cleaned/*.csv.gz` (gzip CSV — no parquet
dependency installed yet; parquet recommended for the ML `processed/` stage).

| File | Rows in → out | All-null rows dropped | Notes |
|---|---|---:|---|
| `city_day` | 29,531 → 28,157 | 1,374 | — |
| `station_day` | 108,035 → 101,148 | 6,887 | — |
| `city_hour` | 707,875 → 657,549 | 50,326 | — |
| `station_hour` | 2,589,083 → 2,352,209 | 236,874 | — |

Value-level cleaning (nulled, **row kept**):

- **`CO` = `NO` mis-fill** — a systematic Kaggle artifact (CO column filled with
  the NO value) across 88 stations. ~1.2 k daily / ~28 k hourly `CO` values
  nulled; `NO` retained.
- **`CO` > 50 mg/m³** — 120 daily / ~3 k hourly nulled as sensor faults.
- **`O3` > 800 µg/m³** — 3 daily / 331 hourly nulled.
- **`AQI` > 1000** — ~90 daily / ~2.7 k hourly nulled as computation errors.
- **`AQI` 501–1000 kept** (450 daily / 41 k hourly) — real severe-episode
  signal; the 500 scale cap is applied only in the UI display layer.

Validation (`data/validation/validation_report.md`): **all checks PASS** on all
four files — non-negative numeric AQI, dates in the 2015–2020 window, no future
dates, no duplicate natural keys, no residual out-of-range concentrations, every
`AQI_bucket` a valid CPCB label consistent with its `AQI`, pollutant medians in
plausible unit bands, zero remaining `CO`=`NO` rows.

## 8. Boundary data acquired

`data/metadata/` now holds geoBoundaries **gbOpen** India (CC-BY 4.0):

| File | Features | Use |
|---|---:|---|
| `geoBoundaries-IND-ADM1_simplified.geojson` | 36 states/UTs (2011 vintage) | state polygons, 3D map |
| `geoBoundaries-IND-ADM2_simplified.geojson` | 735 districts (2021 vintage) | **district assignment** (point-in-polygon on station coords), 3D map |

ADM2 carries only `shapeName` (no parent state), and ADM1 names use diacritics
(`Bihār`, `Chandīgarh`). The station→district step therefore does **two**
independent point-in-polygon joins (ADM1 for state, ADM2 for district) and maps
the diacritic names to our canonical list. That step needs `shapely`
(not yet installed) and station coordinates (from the data.gov.in CPCB
resource — pending the key).

Sources:
[data.gov.in — Real time Air Quality Index](https://www.data.gov.in/catalog/real-time-air-quality-index),
[data.gov.in resource 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69](https://www.data.gov.in/resource/real-time-air-quality-index-various-locations),
[geoBoundaries](https://www.geoboundaries.org/)
