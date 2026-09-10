# SMART AQI - Raw Data Audit

_Generated 2026-09-10T10:07:52 from `archive.zip` (Kaggle: Air Quality Data in India 2015-2020). Inspection only - no rows modified._


## `stations.csv`

- **Rows:** 230
- **Columns:** StationId, StationName, City, State, Status
- **Distinct City:** 127
- **Distinct State:** 21
- **Distinct Status:** 2
- **Distinct State/City pairs:** 127
- **Duplicate rows on key ['StationId']:** 0

| Column | Null % | Placeholder tokens |
|---|---:|---:|
| Status | 42.17 | 97 |

## `city_day.csv`

- **Rows:** 29,531
- **Columns:** City, Date, PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, Benzene, Toluene, Xylene, AQI, AQI_Bucket
- **Date range:** 2015-01-01T00:00:00 -> 2020-07-01T00:00:00 (unparseable: 0, future: 0)
- **Distinct City:** 26
- **Duplicate rows on key ['City', 'Date']:** 0
- **AQI vs AQI_Bucket:** 0 mismatches vs CPCB scale over 24,850 rows; labels = ['Good', 'Moderate', 'Poor', 'Satisfactory', 'Severe', 'Very Poor']

| Column | Null % | Placeholder tokens |
|---|---:|---:|
| PM2.5 | 15.57 | 0 |
| PM10 | 37.72 | 0 |
| NO | 12.13 | 0 |
| NO2 | 12.14 | 0 |
| NOx | 14.17 | 0 |
| NH3 | 34.97 | 0 |
| CO | 6.97 | 0 |
| SO2 | 13.05 | 0 |
| O3 | 13.62 | 0 |
| Benzene | 19.04 | 0 |
| Toluene | 27.23 | 0 |
| Xylene | 61.32 | 0 |
| AQI | 15.85 | 0 |
| AQI_Bucket | 15.85 | 4681 |

| Field | Coverage % | Min | Max | Mean | Neg | > plausible |
|---|---:|---:|---:|---:|---:|---:|
| PM2.5 | 84.43 | 0.04 | 949.99 | 67.5 | 0 | 0 |
| PM10 | 62.28 | 0.01 | 1000.0 | 118.1 | 0 | 0 |
| NO | 87.87 | 0.02 | 390.68 | 17.6 | 0 | 0 |
| NO2 | 87.86 | 0.01 | 362.21 | 28.6 | 0 | 0 |
| NOx | 85.83 | 0.0 | 467.63 | 32.3 | 0 | 0 |
| NH3 | 65.03 | 0.01 | 352.89 | 23.5 | 0 | 0 |
| CO | 93.03 | 0.0 | 175.81 | 2.2 | 0 | 120 |
| SO2 | 86.95 | 0.01 | 193.86 | 14.5 | 0 | 0 |
| O3 | 86.38 | 0.01 | 257.73 | 34.5 | 0 | 0 |
| Benzene | 80.96 | 0.0 | 455.03 | 3.3 | 0 | 0 |
| Toluene | 72.77 | 0.0 | 454.85 | 8.7 | 0 | 0 |
| Xylene | 38.68 | 0.0 | 170.37 | 3.1 | 0 | 0 |
| AQI | 84.15 | 13.0 | 2049.0 | 166.5 | 0 | 93 |

## `station_day.csv`

- **Rows:** 108,035
- **Columns:** StationId, Date, PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, Benzene, Toluene, Xylene, AQI, AQI_Bucket
- **Date range:** 2015-01-01T00:00:00 -> 2020-07-01T00:00:00 (unparseable: 0, future: 0)
- **Distinct StationId:** 110
- **Duplicate rows on key ['StationId', 'Date']:** 0
- **Distinct StationIds:** 110 (not in stations.csv: 0)
- **AQI vs AQI_Bucket:** 0 mismatches vs CPCB scale over 87,025 rows; labels = ['Good', 'Moderate', 'Poor', 'Satisfactory', 'Severe', 'Very Poor']

| Column | Null % | Placeholder tokens |
|---|---:|---:|
| PM2.5 | 20.02 | 0 |
| PM10 | 39.53 | 0 |
| NO | 15.83 | 0 |
| NO2 | 15.32 | 0 |
| NOx | 14.35 | 0 |
| NH3 | 44.53 | 0 |
| CO | 12.03 | 0 |
| SO2 | 23.33 | 0 |
| O3 | 23.67 | 0 |
| Benzene | 29.12 | 0 |
| Toluene | 35.82 | 0 |
| Xylene | 78.81 | 0 |
| AQI | 19.45 | 0 |
| AQI_Bucket | 19.45 | 21010 |

| Field | Coverage % | Min | Max | Mean | Neg | > plausible |
|---|---:|---:|---:|---:|---:|---:|
| PM2.5 | 79.98 | 0.02 | 1000.0 | 80.3 | 0 | 0 |
| PM10 | 60.47 | 0.01 | 1000.0 | 158.0 | 0 | 0 |
| NO | 84.17 | 0.01 | 470.0 | 23.1 | 0 | 0 |
| NO2 | 84.68 | 0.01 | 448.05 | 35.2 | 0 | 0 |
| NOx | 85.65 | 0.0 | 467.63 | 41.2 | 0 | 0 |
| NH3 | 55.47 | 0.01 | 418.9 | 28.7 | 0 | 0 |
| CO | 87.97 | 0.0 | 175.81 | 1.6 | 0 | 120 |
| SO2 | 76.67 | 0.01 | 195.65 | 12.3 | 0 | 0 |
| O3 | 76.33 | 0.01 | 963.0 | 38.1 | 0 | 3 |
| Benzene | 70.88 | 0.0 | 455.03 | 3.4 | 0 | 0 |
| Toluene | 64.18 | 0.0 | 454.85 | 15.3 | 0 | 0 |
| Xylene | 21.19 | 0.0 | 170.37 | 2.4 | 0 | 0 |
| AQI | 80.55 | 8.0 | 2049.0 | 179.7 | 0 | 95 |

## `city_hour.csv`

- **Rows:** 707,875
- **Columns:** City, Datetime, PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, Benzene, Toluene, Xylene, AQI, AQI_Bucket
- **Date range:** 2015-01-01T01:00:00 -> 2020-07-01T00:00:00 (unparseable: 0, future: 0)
- **Distinct City:** 26
- **Duplicate rows on key ['City', 'Datetime']:** 0
- **AQI vs AQI_Bucket:** 0 mismatches vs CPCB scale over 578,795 rows; labels = ['Good', 'Moderate', 'Poor', 'Satisfactory', 'Severe', 'Very Poor']

| Column | Null % | Placeholder tokens |
|---|---:|---:|
| PM2.5 | 20.5 | 0 |
| PM10 | 41.92 | 0 |
| NO | 16.48 | 0 |
| NO2 | 16.55 | 0 |
| NOx | 17.41 | 0 |
| NH3 | 38.5 | 0 |
| CO | 12.22 | 0 |
| SO2 | 18.42 | 0 |
| O3 | 18.25 | 0 |
| Benzene | 23.12 | 0 |
| Toluene | 31.16 | 0 |
| Xylene | 64.39 | 0 |
| AQI | 18.23 | 0 |
| AQI_Bucket | 18.23 | 129080 |

| Field | Coverage % | Min | Max | Mean | Neg | > plausible |
|---|---:|---:|---:|---:|---:|---:|
| PM2.5 | 79.5 | 0.01 | 999.99 | 67.6 | 0 | 0 |
| PM10 | 58.08 | 0.01 | 1000.0 | 119.1 | 0 | 0 |
| NO | 83.52 | 0.01 | 499.99 | 17.4 | 0 | 0 |
| NO2 | 83.45 | 0.01 | 499.51 | 28.9 | 0 | 0 |
| NOx | 82.59 | 0.0 | 498.61 | 32.3 | 0 | 0 |
| NH3 | 61.5 | 0.01 | 499.97 | 23.6 | 0 | 0 |
| CO | 87.78 | 0.0 | 498.57 | 2.2 | 0 | 2978 |
| SO2 | 81.58 | 0.01 | 199.96 | 14.0 | 0 | 0 |
| O3 | 81.75 | 0.01 | 497.62 | 34.8 | 0 | 0 |
| Benzene | 76.88 | 0.0 | 498.07 | 3.1 | 0 | 0 |
| Toluene | 68.84 | 0.0 | 499.4 | 8.7 | 0 | 0 |
| Xylene | 35.61 | 0.0 | 499.99 | 3.1 | 0 | 0 |
| AQI | 81.77 | 8.0 | 3133.0 | 166.4 | 0 | 2665 |

## `station_hour.csv`

- **Rows:** 2,589,083
- **Columns:** StationId, Datetime, PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3, Benzene, Toluene, Xylene, AQI, AQI_Bucket
- **Date range:** 2015-01-01T01:00:00 -> 2020-07-01T00:00:00 (unparseable: 0, future: 0)
- **Distinct StationId:** 110
- **Duplicate rows on key ['StationId', 'Datetime']:** 0
- **Distinct StationIds:** 110 (not in stations.csv: 0)
- **AQI vs AQI_Bucket:** 0 mismatches vs CPCB scale over 2,018,893 rows; labels = ['Good', 'Moderate', 'Poor', 'Satisfactory', 'Severe', 'Very Poor']

| Column | Null % | Placeholder tokens |
|---|---:|---:|
| PM2.5 | 25.02 | 0 |
| PM10 | 43.23 | 0 |
| NO | 21.39 | 0 |
| NO2 | 20.43 | 0 |
| NOx | 18.96 | 0 |
| NH3 | 47.76 | 0 |
| CO | 19.28 | 0 |
| SO2 | 28.69 | 0 |
| O3 | 28.04 | 0 |
| Benzene | 33.28 | 0 |
| Toluene | 40.26 | 0 |
| Xylene | 80.15 | 0 |
| AQI | 22.02 | 0 |
| AQI_Bucket | 22.02 | 570190 |

| Field | Coverage % | Min | Max | Mean | Neg | > plausible |
|---|---:|---:|---:|---:|---:|---:|
| PM2.5 | 74.98 | 0.01 | 1000.0 | 80.9 | 0 | 0 |
| PM10 | 56.77 | 0.01 | 1000.0 | 158.5 | 0 | 0 |
| NO | 78.61 | 0.01 | 500.0 | 22.8 | 0 | 0 |
| NO2 | 79.57 | 0.01 | 499.99 | 35.2 | 0 | 0 |
| NOx | 81.04 | 0.0 | 500.0 | 40.6 | 0 | 0 |
| NH3 | 52.24 | 0.01 | 499.97 | 28.7 | 0 | 0 |
| CO | 80.72 | 0.0 | 498.57 | 1.5 | 0 | 2978 |
| SO2 | 71.31 | 0.01 | 199.96 | 12.1 | 0 | 0 |
| O3 | 71.96 | 0.01 | 997.0 | 38.1 | 0 | 331 |
| Benzene | 66.72 | 0.0 | 498.07 | 3.3 | 0 | 0 |
| Toluene | 59.74 | 0.0 | 499.99 | 14.9 | 0 | 0 |
| Xylene | 19.85 | 0.0 | 499.99 | 2.4 | 0 | 0 |
| AQI | 77.98 | 5.0 | 3133.0 | 180.2 | 0 | 2728 |