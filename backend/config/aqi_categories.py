"""
Central definition of the Indian National Air Quality Index (CPCB) category
scale. This is the single source of truth for AQI thresholds across the whole
project (cleaning pipeline, ML labelling, API, frontend copy).

Reference: CPCB National Air Quality Index, launched 2015. The AQI value is a
0-500 index; sub-indices are computed per pollutant and the overall AQI is the
maximum sub-index. The six categories below are the official breakpoints.

The Kaggle dataset's own ``AQI_Bucket`` column was verified (see
``data/validation/raw_audit.md``) to match this table with zero mismatches, so
adopting it verbatim keeps us consistent with the source data.
"""
from __future__ import annotations

from typing import Optional, TypedDict


class AQICategory(TypedDict):
    label: str
    lo: int          # inclusive lower bound of the AQI value
    hi: int          # inclusive upper bound
    color: str       # semantic colour (CPCB-aligned), NOT the brand purple
    concern: str     # short health-concern phrase


# Ordered best -> worst. ``hi`` of the final band is an open-ended cap.
AQI_CATEGORIES: list[AQICategory] = [
    {"label": "Good",         "lo": 0,   "hi": 50,  "color": "#2E9E4F",
     "concern": "Minimal impact."},
    {"label": "Satisfactory", "lo": 51,  "hi": 100, "color": "#7BB93F",
     "concern": "Minor breathing discomfort to sensitive people."},
    {"label": "Moderate",     "lo": 101, "hi": 200, "color": "#F0C030",
     "concern": "Breathing discomfort to people with lung/heart disease, "
                "children and older adults."},
    {"label": "Poor",         "lo": 201, "hi": 300, "color": "#F08B24",
     "concern": "Breathing discomfort to most people on prolonged exposure."},
    {"label": "Very Poor",    "lo": 301, "hi": 400, "color": "#E24B4B",
     "concern": "Respiratory illness on prolonged exposure."},
    {"label": "Severe",       "lo": 401, "hi": 500, "color": "#8B2E8B",
     "concern": "Affects healthy people and seriously impacts those with "
                "existing disease."},
]

# Values above this are treated as the top band but flagged as out-of-range
# by the validation pipeline.
AQI_MAX_EXPECTED = 500

_LABELS = [c["label"] for c in AQI_CATEGORIES]


def categorize(aqi: Optional[float]) -> Optional[str]:
    """Map a numeric AQI to its CPCB category label. ``None`` in -> ``None`` out."""
    if aqi is None:
        return None
    try:
        v = float(aqi)
    except (TypeError, ValueError):
        return None
    if v != v or v < 0:          # NaN or negative
        return None
    for cat in AQI_CATEGORIES:
        if v <= cat["hi"]:
            return cat["label"]
    return AQI_CATEGORIES[-1]["label"]   # >= 401 (incl. > 500)


def category_meta(label: Optional[str]) -> Optional[AQICategory]:
    for cat in AQI_CATEGORIES:
        if cat["label"] == label:
            return cat
    return None


def is_valid_label(label: str) -> bool:
    return label in _LABELS
