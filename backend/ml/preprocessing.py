"""
Shared ML preprocessing for SMART AQI.

Pipeline (see docs/ml_pipeline.md):

  cleaned station-hour panel  (data/cleaned/station_hour.csv.gz)
        |  aggregate to station-day (rich daily features from hourly signal)
  station-day panel
        |  per-station lag / rolling / calendar features
  feature table
        |  chronological split by TARGET date (no shuffling)
  train / val / test  +  fitted scalers  +  daily sequences for the RNN/Transformer

Design note: the models step at DAILY resolution even though the source grain is
hourly. The product is a 7-day daily forecast; hourly 168-step recursion both
explodes error and is intractable to train on CPU. Aggregating the hourly panel
keeps its signal (daily mean/max/min/std, diurnal range, valid-hour counts)
while keeping the modelling target daily. This refines - does not discard - the
"station-hour pooled panel" decision in docs/dataset.md section 6.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "cleaned"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

POLLUTANTS = ["PM25", "PM10", "NO", "NO2", "NOx", "NH3", "CO", "SO2", "O3"]
WEATHER_COLS = ["temp_mean", "temp_max", "temp_min", "humidity",
                "wind_mean", "wind_max", "pressure", "rain"]
WEATHER_FILE = PROCESSED / "weather_history.parquet"

# chronological split boundaries (target date)
TRAIN_END = pd.Timestamp("2019-06-30")
VAL_END = pd.Timestamp("2019-12-31")
# test = everything after VAL_END (data ends 2020-07-01)

SEQ_WINDOW = 21          # daily steps fed to the sequence models
MIN_STATION_DAYS = 250   # stations with fewer usable target days are dropped
MIN_HOURS_FOR_DAY = 4    # min non-null hourly AQI to trust a day's AQI


@dataclass
class Dataset:
    """Everything the training script needs."""
    # flat feature table (one row per station-day with a known next-day target)
    flat: pd.DataFrame
    feature_cols: list[str]
    seq_feature_cols: list[str]
    target_col: str = "target_AQI"
    # sequence tensors, aligned with flat rows that carry `has_seq == True`
    seq_X: dict[str, np.ndarray] = field(default_factory=dict)   # split -> (N,W,F)
    seq_station: dict[str, np.ndarray] = field(default_factory=dict)
    seq_y: dict[str, np.ndarray] = field(default_factory=dict)
    station_index: dict[str, int] = field(default_factory=dict)
    scalers: dict = field(default_factory=dict)


# --------------------------------------------------------------- daily panel --
def _season(month: int) -> str:
    return {12: "winter", 1: "winter", 2: "winter",
            3: "summer", 4: "summer", 5: "summer",
            6: "monsoon", 7: "monsoon", 8: "monsoon", 9: "monsoon",
            10: "post_monsoon", 11: "post_monsoon"}[month]


def build_daily_panel(hourly_path: Path | None = None) -> pd.DataFrame:
    """Aggregate the cleaned hourly station panel to one row per station-day."""
    path = hourly_path or (CLEAN / "station_hour.csv.gz")
    df = pd.read_csv(path, low_memory=False,
                     usecols=["state", "city", "station", "station_id", "date",
                              "AQI"] + POLLUTANTS)
    df["ts"] = pd.to_datetime(df["date"])
    df["day"] = df["ts"].dt.floor("D")

    agg = {p: "mean" for p in POLLUTANTS}
    agg["AQI"] = "mean"
    g = df.groupby(["station_id", "day"], sort=True)
    daily = g.agg(agg)
    extra = g.agg(
        AQI_max=("AQI", "max"), AQI_min=("AQI", "min"), AQI_std=("AQI", "std"),
        PM25_max=("PM25", "max"), PM10_max=("PM10", "max"),
        n_hours_aqi=("AQI", "count"),
    )
    daily = daily.join(extra).reset_index()
    daily["diurnal_range"] = daily["AQI_max"] - daily["AQI_min"]

    meta = (df.sort_values("ts")
              .groupby("station_id")[["state", "city", "station"]]
              .first())
    daily = daily.merge(meta, on="station_id", how="left")

    # a day's AQI is only trustworthy with enough hourly coverage
    daily.loc[daily["n_hours_aqi"] < MIN_HOURS_FOR_DAY, "AQI"] = np.nan
    daily = daily.rename(columns={"day": "date"})
    daily = daily.sort_values(["station_id", "date"]).reset_index(drop=True)

    # --- join historical weather where available (Open-Meteo archive) ---
    if WEATHER_FILE.exists():
        wx = pd.read_parquet(WEATHER_FILE)
        wx["date"] = pd.to_datetime(wx["date"])
        daily = daily.merge(wx, on=["station_id", "date"], how="left")
        n_wx = int(daily["temp_mean"].notna().sum())
        print(f"  weather joined: {n_wx:,}/{len(daily):,} station-days "
              f"({daily.loc[daily['temp_mean'].notna(), 'station_id'].nunique()} stations)")
    else:
        for c in WEATHER_COLS:
            daily[c] = np.nan
    return daily


# ------------------------------------------------------------- feature table --
def add_features(daily: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sid, g in daily.groupby("station_id", sort=False):
        g = g.sort_values("date").copy()
        # continuous daily index so lags respect real calendar gaps
        g = g.set_index("date").asfreq("D")
        g["station_id"] = sid
        a = g["AQI"]
        for k in (1, 2, 3, 7):
            g[f"AQI_lag_{k}"] = a.shift(k)
        g["AQI_roll_mean_3"] = a.shift(1).rolling(3, min_periods=2).mean()
        g["AQI_roll_mean_7"] = a.shift(1).rolling(7, min_periods=3).mean()
        g["AQI_roll_std_7"] = a.shift(1).rolling(7, min_periods=3).std()
        g["target_AQI"] = a.shift(-1)          # predict next day
        out.append(g.reset_index())
    feat = pd.concat(out, ignore_index=True)

    feat["dow"] = feat["date"].dt.dayofweek
    feat["month"] = feat["date"].dt.month
    feat["doy"] = feat["date"].dt.dayofyear
    feat["doy_sin"] = np.sin(2 * np.pi * feat["doy"] / 365.25)
    feat["doy_cos"] = np.cos(2 * np.pi * feat["doy"] / 365.25)
    feat["season"] = feat["month"].map(_season)
    feat = pd.get_dummies(feat, columns=["season"], prefix="seas", dtype=float)

    feat["split"] = np.where(feat["date"] <= TRAIN_END, "train",
                     np.where(feat["date"] <= VAL_END, "val", "test"))
    return feat


CONTEMP = POLLUTANTS + ["PM25_max", "PM10_max", "AQI_std", "diurnal_range",
                        "n_hours_aqi"] + WEATHER_COLS
LAGROLL = ["AQI_lag_1", "AQI_lag_2", "AQI_lag_3", "AQI_lag_7",
           "AQI_roll_mean_3", "AQI_roll_mean_7", "AQI_roll_std_7"]
CALENDAR = ["dow", "month", "doy_sin", "doy_cos",
            "seas_winter", "seas_summer", "seas_monsoon", "seas_post_monsoon"]
SEQ_FEATURES = ["AQI", "PM25", "PM10", "NO2", "SO2", "CO", "O3",
                "wind_mean", "temp_mean", "rain",
                "doy_sin", "doy_cos", "dow"]


def make_dataset(save: bool = True) -> Dataset:
    daily = build_daily_panel()
    feat = add_features(daily)

    # keep only rows with a target and the essential lag history
    need = ["target_AQI", "AQI_lag_1", "AQI_lag_7"]
    model_rows = feat.dropna(subset=need).copy()

    # drop thin stations
    keep = (model_rows.groupby("station_id")["target_AQI"].count()
            >= MIN_STATION_DAYS)
    keep_ids = set(keep[keep].index)
    model_rows = model_rows[model_rows["station_id"].isin(keep_ids)].copy()
    for c in [c for c in feat.columns if "seas_" in c]:
        if c not in model_rows:
            model_rows[c] = 0.0

    feature_cols = [c for c in CONTEMP + LAGROLL + CALENDAR
                    if c in model_rows.columns]
    station_index = {s: i for i, s in enumerate(sorted(keep_ids))}
    model_rows["station_idx"] = model_rows["station_id"].map(station_index)

    # ---- scalers (fit on TRAIN only) ----
    from sklearn.preprocessing import StandardScaler
    tr = model_rows[model_rows.split == "train"]
    feat_median = tr[feature_cols].median().to_dict()
    seq_median = tr[SEQ_FEATURES].median().to_dict()
    # fit on plain ndarrays so later .transform(ndarray) calls stay quiet
    feat_scaler = StandardScaler().fit(
        tr[feature_cols].astype(float).fillna(feat_median).to_numpy())
    tgt_scaler = StandardScaler().fit(
        tr[["target_AQI"]].astype(float).to_numpy())
    seq_scaler = StandardScaler().fit(
        tr[SEQ_FEATURES].astype(float).fillna(seq_median).to_numpy())

    ds = Dataset(flat=model_rows, feature_cols=feature_cols,
                 seq_feature_cols=SEQ_FEATURES, station_index=station_index)
    ds.scalers = {"features": feat_scaler, "target": tgt_scaler,
                  "feat_median": feat_median, "sequence": seq_scaler,
                  "seq_median": seq_median}

    # ---- daily sequences per split (window fully precedes the target day) ----
    full = feat[feat["station_id"].isin(keep_ids)].copy()
    full = full.sort_values(["station_id", "date"])
    full["station_idx"] = full["station_id"].map(station_index)
    seqX = {"train": [], "val": [], "test": []}
    seqS = {"train": [], "val": [], "test": []}
    seqY = {"train": [], "val": [], "test": []}
    W = SEQ_WINDOW
    for sid, g in full.groupby("station_id", sort=False):
        g = g.reset_index(drop=True)
        arr = g[SEQ_FEATURES].astype(float)
        arr = arr.fillna(pd.Series(seq_median)).to_numpy()
        arr = seq_scaler.transform(arr)
        tgt = g["target_AQI"].to_numpy(dtype=float)
        spl = g["split"].to_numpy()
        sidx = int(g["station_idx"].iloc[0])
        for t in range(W, len(g)):
            y = tgt[t - 1]                       # target aligned to day t-1's "next day"
            if not np.isfinite(y):
                continue
            window = arr[t - W:t]
            if not np.isfinite(window).all():
                continue
            s = spl[t - 1]
            seqX[s].append(window)
            seqS[s].append(sidx)
            seqY[s].append(y)
    for s in ("train", "val", "test"):
        ds.seq_X[s] = np.asarray(seqX[s], dtype="float32")
        ds.seq_station[s] = np.asarray(seqS[s], dtype="int32")
        ds.seq_y[s] = tgt_scaler.transform(
            np.asarray(seqY[s], dtype="float32").reshape(-1, 1)).ravel()

    if save:
        _save(ds)
    return ds


def _save(ds: Dataset) -> None:
    import joblib
    ds.flat.to_parquet(PROCESSED / "feature_table.parquet", index=False)
    for s in ("train", "val", "test"):
        np.savez_compressed(PROCESSED / f"seq_{s}.npz",
                            X=ds.seq_X[s], station=ds.seq_station[s],
                            y=ds.seq_y[s])
    joblib.dump(ds.scalers, PROCESSED / "scalers.joblib")
    meta = {
        "seq_window": SEQ_WINDOW,
        "feature_cols": ds.feature_cols,
        "seq_feature_cols": ds.seq_feature_cols,
        "station_index": ds.station_index,
        "n_stations": len(ds.station_index),
        "split": {"train_end": str(TRAIN_END.date()),
                  "val_end": str(VAL_END.date()),
                  "test": "2020-01-01 .. 2020-07-01"},
        "rows": {s: int((ds.flat.split == s).sum())
                 for s in ("train", "val", "test")},
        "seq_rows": {s: int(ds.seq_X[s].shape[0])
                     for s in ("train", "val", "test")},
    }
    (PROCESSED / "feature_config.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    d = make_dataset(save=True)
    print("flat rows :", {s: int((d.flat.split == s).sum())
                          for s in ("train", "val", "test")})
    print("seq rows  :", {s: d.seq_X[s].shape for s in ("train", "val", "test")})
    print("stations  :", len(d.station_index))
    print("features  :", len(d.feature_cols), d.feature_cols)
