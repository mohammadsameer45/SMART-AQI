"""
CPCB National Air Quality Index sub-index breakpoints and the AQI computation.

The overall AQI is the **maximum** of the available pollutant sub-indices, each
obtained by piecewise-linear interpolation between the CPCB breakpoints below.
Averaging periods per the CPCB method: 24 h for PM2.5, PM10, SO2, NO2, NH3, Pb;
8 h for CO and O3.

Units: µg/m³ for all pollutants except CO, which is mg/m³.

NOTE: the data.gov.in live resource publishes the latest station readings
(`pollutant_avg`), not guaranteed rolling averages, so an AQI computed from it is
labelled "computed (CPCB sub-index method)" rather than presented as the
official portal value.
"""
from __future__ import annotations

from typing import Optional

# pollutant -> list of (Clo, Chi, Ilo, Ihi)
BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "PM25": [(0, 30, 0, 50), (30, 60, 51, 100), (60, 90, 101, 200),
             (90, 120, 201, 300), (120, 250, 301, 400), (250, 500, 401, 500)],
    "PM10": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 250, 101, 200),
             (250, 350, 201, 300), (350, 430, 301, 400), (430, 600, 401, 500)],
    "NO2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 180, 101, 200),
            (180, 280, 201, 300), (280, 400, 301, 400), (400, 500, 401, 500)],
    "O3": [(0, 50, 0, 50), (50, 100, 51, 100), (100, 168, 101, 200),
           (168, 208, 201, 300), (208, 748, 301, 400), (748, 1000, 401, 500)],
    "CO": [(0, 1.0, 0, 50), (1.0, 2.0, 51, 100), (2.0, 10, 101, 200),
           (10, 17, 201, 300), (17, 34, 301, 400), (34, 50, 401, 500)],
    "SO2": [(0, 40, 0, 50), (40, 80, 51, 100), (80, 380, 101, 200),
            (380, 800, 201, 300), (800, 1600, 301, 400), (1600, 2000, 401, 500)],
    "NH3": [(0, 200, 0, 50), (200, 400, 51, 100), (400, 800, 101, 200),
            (800, 1200, 201, 300), (1200, 1800, 301, 400), (1800, 2400, 401, 500)],
}

# maps the data.gov.in `pollutant_id` values to our canonical keys
POLLUTANT_ID_MAP = {
    "PM2.5": "PM25", "PM10": "PM10", "NO2": "NO2", "SO2": "SO2",
    "CO": "CO", "OZONE": "O3", "O3": "O3", "NH3": "NH3",
}


def sub_index(pollutant: str, conc: Optional[float]) -> Optional[float]:
    if conc is None or conc != conc or conc < 0:
        return None
    table = BREAKPOINTS.get(pollutant)
    if not table:
        return None
    for clo, chi, ilo, ihi in table:
        if clo <= conc <= chi:
            return round(ilo + (ihi - ilo) * (conc - clo) / (chi - clo), 1)
    # above the top band → cap at the top sub-index (matches CPCB "500+" handling)
    return float(table[-1][3])


def compute_aqi(concentrations: dict[str, Optional[float]]
                ) -> tuple[Optional[float], dict[str, float], Optional[str]]:
    """Return (aqi, sub_indices, note).

    CPCB rule: AQI requires at least one of PM2.5 / PM10 and a minimum of three
    pollutants overall; otherwise it is not reported.
    """
    subs = {}
    for p, c in concentrations.items():
        si = sub_index(p, c)
        if si is not None:
            subs[p] = si
    if not subs:
        return None, {}, "no valid pollutant readings"
    has_pm = any(p in subs for p in ("PM25", "PM10"))
    if not has_pm or len(subs) < 3:
        return None, subs, "insufficient pollutants for a CPCB AQI (need PM + ≥3)"
    aqi = max(subs.values())
    return round(aqi, 0), subs, None
