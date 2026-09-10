# SMART AQI - Cleaning Report

_Generated 2026-09-10T10:29:16 by `scripts/clean_data.py`. Missing measurements are left null - never imputed or fabricated._


## `city_day.csv` -> `city_day.csv.gz` (day)

- Rows: **29,531 -> 28,157**
- Date range: 2015-01-01 -> 2020-07-01
- Distinct: 21 states, 26 cities, 0 stations
- Dropped (all measures null): 1,374
- Dropped (bad/future date): 0
- Duplicates removed: 0
- Values nulled as implausible: {'CO': 120, 'CO_equals_NO_misfill': 1202, 'AQI': 93}
- AQI values above scale cap 500 (kept as real severe-episode signal): 450
- Missing % after clean: {'PM25': 11.45, 'PM10': 34.68, 'NO': 7.84, 'NO2': 7.85, 'NOx': 9.98, 'NH3': 31.8, 'CO': 7.13, 'SO2': 8.81, 'O3': 9.4, 'Benzene': 15.09, 'Toluene': 23.68, 'Xylene': 59.43, 'AQI': 12.08}

  Records per state: Tamil Nadu (2,373), Andhra Pradesh (2,326), Delhi (2,009), Karnataka (2,008), Telangana (2,003), Uttar Pradesh (1,991), Maharashtra (1,989), Bihar (1,709), Haryana (1,622), Odisha (1,608), Gujarat (1,559), Kerala (1,420), Punjab (1,195), Rajasthan (1,108), Jharkhand (947), West Bengal (814), Assam (502), Chandigarh (304), Madhya Pradesh (280), Meghalaya (277), Mizoram (113)

## `station_day.csv` -> `station_day.csv.gz` (day)

- Rows: **108,035 -> 101,148**
- Date range: 2015-01-01 -> 2020-07-01
- Distinct: 21 states, 26 cities, 110 stations
- Dropped (all measures null): 6,887
- Dropped (bad/future date): 0
- Duplicates removed: 0
- Values nulled as implausible: {'CO': 120, 'O3': 3, 'CO_equals_NO_misfill': 1225, 'AQI': 95}
- AQI values above scale cap 500 (kept as real severe-episode signal): 1,788
- Missing % after clean: {'PM25': 14.57, 'PM10': 35.41, 'NO': 10.1, 'NO2': 9.55, 'NOx': 8.52, 'NH3': 40.75, 'CO': 7.37, 'SO2': 18.11, 'O3': 18.47, 'Benzene': 24.29, 'Toluene': 31.45, 'Xylene': 77.36, 'AQI': 14.06}

  Records per state: Delhi (42,016), Karnataka (11,263), Telangana (8,397), Tamil Nadu (6,477), Uttar Pradesh (5,846), Maharashtra (5,252), West Bengal (3,122), Rajasthan (3,066), Haryana (2,615), Bihar (2,432), Andhra Pradesh (2,326), Odisha (1,608), Gujarat (1,559), Kerala (1,551), Punjab (1,195), Jharkhand (947), Assam (502), Chandigarh (304), Madhya Pradesh (280), Meghalaya (277), Mizoram (113)

## `city_hour.csv` -> `city_hour.csv.gz` (hour)

- Rows: **707,875 -> 657,549**
- Date range: 2015-01-01T01:00:00 -> 2020-07-01T00:00:00
- Distinct: 21 states, 26 cities, 0 stations
- Dropped (all measures null): 50,326
- Dropped (bad/future date): 0
- Duplicates removed: 0
- Values nulled as implausible: {'CO': 2978, 'CO_equals_NO_misfill': 26897, 'AQI': 2665}
- AQI values above scale cap 500 (kept as real severe-episode signal): 8,470
- Missing % after clean: {'PM25': 14.41, 'PM10': 37.47, 'NO': 10.08, 'NO2': 10.16, 'NOx': 11.09, 'NH3': 33.79, 'CO': 10.05, 'SO2': 12.17, 'O3': 12.0, 'Benzene': 17.23, 'Toluene': 25.9, 'Xylene': 61.67, 'AQI': 12.38}

  Records per state: Tamil Nadu (56,440), Andhra Pradesh (53,268), Delhi (48,178), Karnataka (47,993), Telangana (47,844), Uttar Pradesh (47,487), Maharashtra (46,799), Bihar (37,890), Haryana (37,161), Odisha (36,413), Gujarat (36,192), Kerala (33,382), Punjab (27,538), Rajasthan (26,327), Jharkhand (20,178), West Bengal (19,490), Assam (11,911), Chandigarh (7,222), Madhya Pradesh (6,649), Meghalaya (6,507), Mizoram (2,680)

## `station_hour.csv` -> `station_hour.csv.gz` (hour)

- Rows: **2,589,083 -> 2,352,209**
- Date range: 2015-01-01T01:00:00 -> 2020-07-01T00:00:00
- Distinct: 21 states, 26 cities, 110 stations
- Dropped (all measures null): 236,874
- Dropped (bad/future date): 0
- Duplicates removed: 0
- Values nulled as implausible: {'CO': 2978, 'O3': 331, 'CO_equals_NO_misfill': 28516, 'AQI': 2728}
- AQI values above scale cap 500 (kept as real severe-episode signal): 41,033
- Missing % after clean: {'PM25': 17.47, 'PM10': 37.51, 'NO': 13.47, 'NO2': 12.42, 'NOx': 10.8, 'NH3': 42.5, 'CO': 12.5, 'SO2': 21.51, 'O3': 20.81, 'Benzene': 26.56, 'Toluene': 34.24, 'Xylene': 78.15, 'AQI': 14.29}

  Records per state: Delhi (985,542), Karnataka (254,557), Telangana (195,726), Tamil Nadu (150,881), Uttar Pradesh (136,282), Maharashtra (124,049), West Bengal (73,546), Rajasthan (72,245), Haryana (59,938), Bihar (54,622), Andhra Pradesh (53,268), Odisha (36,413), Kerala (36,263), Gujarat (36,192), Punjab (27,538), Jharkhand (20,178), Assam (11,911), Chandigarh (7,222), Madhya Pradesh (6,649), Meghalaya (6,507), Mizoram (2,680)