"""
Geographic resolution for SMART AQI.

LGD provides the complete administrative State -> District hierarchy.
The official LGD district CSV is stored locally at:

    data/lgd_districts.csv

MongoDB/CPCB provides actual AQI monitoring coverage.

Therefore:

    LGD CSV  = all legitimate administrative districts
    MongoDB  = districts/cities/stations that actually have AQI data

We never fabricate AQI data for an unmonitored district.
"""

from __future__ import annotations

import csv
from functools import lru_cache
from typing import Any

from backend.config.settings import config
from backend.models import mongo_models as M
from backend.utils.responses import ApiError


# ============================================================================
# CONFIGURATION
# ============================================================================

# Project root /data/lgd_districts.csv
LGD_CSV_PATH = config.DATA_DIR / "lgd_districts.csv"


# ============================================================================
# NORMALIZATION HELPERS
# ============================================================================

def _normalise(value: Any) -> str:
    """
    Normalize a value for safe comparison.

    Examples:

        "Andhra Pradesh" -> "andhra pradesh"
        "  Andhra   Pradesh " -> "andhra pradesh"
    """
    return " ".join(
        str(value or "").strip().lower().split()
    )


def _normalise_header(value: Any) -> str:
    """
    Normalize CSV column headers.

    This allows common variations such as:

        state_name
        State Name
        STATE NAME
        State_Name
        state-name

    to be treated consistently.
    """

    text = str(value or "").strip().lower()

    for char in (
        " ",
        "-",
        "(",
        ")",
        "/",
        ".",
    ):
        text = text.replace(char, "_")

    while "__" in text:
        text = text.replace("__", "_")

    return text.strip("_")


# ============================================================================
# LOCAL LGD CSV LOADER
# ============================================================================

@lru_cache(maxsize=1)
def _get_lgd_districts() -> list[dict[str, str]]:
    """
    Read the official LGD district CSV.

    The CSV is loaded once and cached in memory.

    This is intentionally NOT calling data.gov.in on every request.
    """

    # ------------------------------------------------------------------------
    # Check whether the file exists
    # ------------------------------------------------------------------------

    if not LGD_CSV_PATH.exists():
        raise ApiError(
            "lgd_file_missing",
            (
                "LGD district file was not found at: "
                f"{LGD_CSV_PATH}"
            ),
            500,
        )

    # ------------------------------------------------------------------------
    # Read CSV
    # ------------------------------------------------------------------------

    try:

        with LGD_CSV_PATH.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            # ---------------------------------------------------------------
            # Validate headers
            # ---------------------------------------------------------------

            if not reader.fieldnames:

                raise ApiError(
                    "lgd_invalid_file",
                    "LGD CSV does not contain a header row.",
                    500,
                )

            # Diagnostic output.
            # This is useful during setup and can be removed later.
            print(
                "LGD CSV headers:",
                reader.fieldnames,
            )

            # ---------------------------------------------------------------
            # Normalize headers
            # ---------------------------------------------------------------

            header_map = {
                _normalise_header(name): name
                for name in reader.fieldnames
                if name
            }

            # ---------------------------------------------------------------
            # Locate state column
            # ---------------------------------------------------------------

            state_column = None

            for key, original in header_map.items():

                if key in {
                    "state_name",
                    "statename",
                    "state_name_in_english",
                    "state",
                }:

                    state_column = original
                    break

                if key.startswith("state_name"):

                    state_column = original
                    break

            # ---------------------------------------------------------------
            # Locate district column
            # ---------------------------------------------------------------

            district_column = None

            for key, original in header_map.items():

                if key in {
                    "district_name",
                    "districtname",
                    "district_name_in_english",
                    "district",
                }:

                    district_column = original
                    break

                if key.startswith("district_name"):

                    district_column = original
                    break

            # ---------------------------------------------------------------
            # Validate required columns
            # ---------------------------------------------------------------

            if not state_column or not district_column:

                raise ApiError(
                    "lgd_invalid_file",
                    (
                        "LGD CSV must contain state and district "
                        "name columns. "
                        f"Detected headers: {reader.fieldnames}"
                    ),
                    500,
                )

            print(
                "LGD state column:",
                state_column,
            )

            print(
                "LGD district column:",
                district_column,
            )

            # ---------------------------------------------------------------
            # Read records
            # ---------------------------------------------------------------

            records: list[dict[str, str]] = []

            for row in reader:

                if not isinstance(row, dict):
                    continue

                state_name = str(
                    row.get(state_column, "")
                ).strip()

                district_name = str(
                    row.get(district_column, "")
                ).strip()

                # Ignore incomplete rows.
                if not state_name or not district_name:
                    continue

                records.append(
                    {
                        "state_name": state_name,
                        "district_name": district_name,
                    }
                )

            # ---------------------------------------------------------------
            # Make sure records were found
            # ---------------------------------------------------------------

            if not records:

                raise ApiError(
                    "lgd_invalid_file",
                    (
                        "LGD CSV contains no usable district "
                        "records."
                    ),
                    500,
                )

            print(
                f"LGD district records loaded: {len(records)}"
            )

            return records

    # ------------------------------------------------------------------------
    # API errors should pass through unchanged
    # ------------------------------------------------------------------------

    except ApiError:
        raise

    # ------------------------------------------------------------------------
    # File-system error
    # ------------------------------------------------------------------------

    except OSError as exc:

        raise ApiError(
            "lgd_file_error",
            (
                "Unable to read LGD district file: "
                f"{exc}"
            ),
            500,
        )

    # ------------------------------------------------------------------------
    # CSV parsing error
    # ------------------------------------------------------------------------

    except csv.Error as exc:

        raise ApiError(
            "lgd_invalid_file",
            (
                "Unable to parse LGD CSV: "
                f"{exc}"
            ),
            500,
        )


# ============================================================================
# LGD DISTRICTS FOR A STATE
# ============================================================================

def _lgd_districts_for_state(
    state: str,
) -> list[str]:
    """
    Return all official LGD districts belonging to a state.
    """

    records = _get_lgd_districts()

    wanted_state = _normalise(state)

    districts: dict[str, str] = {}

    for record in records:

        state_name = record.get(
            "state_name"
        )

        district_name = record.get(
            "district_name"
        )

        if not state_name or not district_name:
            continue

        # Compare normalized state names.
        if _normalise(state_name) != wanted_state:
            continue

        # Use normalized district name as the
        # duplicate-detection key.
        key = _normalise(district_name)

        # Preserve official spelling.
        if key not in districts:

            districts[key] = (
                district_name.strip()
            )

    return sorted(
        districts.values(),
        key=str.casefold,
    )


# ============================================================================
# STATES
# ============================================================================

def list_states() -> list[str]:
    """
    Return states currently known to the application.

    We intentionally keep the existing MongoDB behaviour here so that
    existing application functionality is not disturbed.

    Later, if required, the state list can also be sourced from LGD.
    """

    return M.list_states()


# ============================================================================
# STATE -> DISTRICTS
# ============================================================================

def areas_for_state(
    state: str,
) -> dict[str, Any]:
    """
    Return ALL administrative districts for a state.

    Source:

        data/lgd_districts.csv

    MongoDB is NOT used to decide which administrative districts exist.

    MongoDB is only used later to determine actual AQI monitoring coverage.
    """

    # ------------------------------------------------------------------------
    # Get states currently known to the application
    # ------------------------------------------------------------------------

    known_states = M.list_states()

    # ------------------------------------------------------------------------
    # Find canonical state spelling
    # ------------------------------------------------------------------------

    matching_state = next(
        (
            s
            for s in known_states
            if _normalise(s) == _normalise(state)
        ),
        None,
    )

    # ------------------------------------------------------------------------
    # Unknown state
    # ------------------------------------------------------------------------

    if not matching_state:

        raise ApiError(
            "unknown_state",
            f"No data for state '{state}'",
            404,
        )

    # ------------------------------------------------------------------------
    # Read districts from official LGD CSV
    # ------------------------------------------------------------------------

    lgd_districts = _lgd_districts_for_state(
        matching_state
    )

    # ------------------------------------------------------------------------
    # If LGD contains districts, return them
    # ------------------------------------------------------------------------

    if lgd_districts:

        return {
            "level": "district",
            "items": lgd_districts,
        }

    # ------------------------------------------------------------------------
    # Safe fallback:
    #
    # If the LGD CSV does not contain the requested state,
    # preserve the previous MongoDB behaviour.
    # ------------------------------------------------------------------------

    districts = sorted(
        d
        for d in M.col(
            M.LOCATIONS
        ).distinct(
            "district",
            {
                "state": matching_state
            },
        )
        if d
    )

    if districts:

        return {
            "level": "district",
            "items": districts,
        }

    # ------------------------------------------------------------------------
    # Final fallback to cities
    # ------------------------------------------------------------------------

    cities = sorted(
        c
        for c in M.col(
            M.LOCATIONS
        ).distinct(
            "city",
            {
                "state": matching_state
            },
        )
        if c
    )

    return {
        "level": "city",
        "items": cities,
    }


# ============================================================================
# DISTRICT/CITY -> MONITORING LOCATIONS
# ============================================================================

def resolve_area(
    state: str,
    area: str,
) -> dict[str, Any]:
    """
    Resolve an administrative district/city.

    LGD determines whether a district legitimately exists.

    MongoDB determines whether AQI monitoring data exists.

    Therefore an LGD district with no MongoDB monitoring record is still a
    valid area; it simply has zero monitoring coverage.

    No fake AQI data is created.
    """

    # ------------------------------------------------------------------------
    # Canonical state spelling
    # ------------------------------------------------------------------------

    known_states = M.list_states()

    matching_state = next(
        (
            s
            for s in known_states
            if _normalise(s) == _normalise(state)
        ),
        None,
    )

    if not matching_state:

        raise ApiError(
            "unknown_state",
            f"No data for state '{state}'",
            404,
        )

    # ------------------------------------------------------------------------
    # First try MongoDB monitoring locations.
    #
    # These represent actual historical/station coverage.
    # ------------------------------------------------------------------------

    q = {
        "state": matching_state,
        "$or": [
            {
                "district": area
            },
            {
                "city": area
            },
        ],
    }

    docs = list(
        M.col(
            M.LOCATIONS
        ).find(
            q,
            {
                "_id": 0
            },
        )
    )

    # ------------------------------------------------------------------------
    # MongoDB has monitoring records.
    # ------------------------------------------------------------------------

    if docs:

        matched_level = (
            "district"
            if any(
                _normalise(d.get("district"))
                == _normalise(area)
                for d in docs
            )
            else "city"
        )

        # ---------------------------------------------------------------
        # Extract monitoring stations
        # ---------------------------------------------------------------

        stations = sorted(
            {
                d["station_id"]
                for d in docs
                if d.get("station_id")
            }
        )

        # ---------------------------------------------------------------
        # Extract cities
        # ---------------------------------------------------------------

        cities = sorted(
            {
                d["city"]
                for d in docs
                if d.get("city")
            }
        )

        return {
            "state": matching_state,
            "area": area,
            "matched_level": matched_level,
            "administrative_exists": True,
            "monitoring_available": True,
            "location_docs": docs,
            "stations": stations,
            "cities": cities,
        }

    # ------------------------------------------------------------------------
    # No MongoDB monitoring record.
    #
    # Check whether the requested area is a legitimate LGD district.
    # ------------------------------------------------------------------------

    lgd_districts = _lgd_districts_for_state(
        matching_state
    )

    lgd_match = next(
        (
            district
            for district in lgd_districts
            if _normalise(district)
            == _normalise(area)
        ),
        None,
    )

    # ------------------------------------------------------------------------
    # Valid LGD district but no monitoring coverage.
    # ------------------------------------------------------------------------

    if lgd_match:

        return {
            "state": matching_state,
            "area": lgd_match,
            "matched_level": "district",
            "administrative_exists": True,
            "monitoring_available": False,
            "location_docs": [],
            "stations": [],
            "cities": [],
        }

    # ------------------------------------------------------------------------
    # It may be a MongoDB city that isn't represented as an LGD district.
    #
    # This preserves compatibility with existing city-level historical data.
    # ------------------------------------------------------------------------

    city_exists = M.col(
        M.LOCATIONS
    ).find_one(
        {
            "state": matching_state,
            "city": area,
        },
        {
            "_id": 1,
        },
    )

    if city_exists:

        return {
            "state": matching_state,
            "area": area,
            "matched_level": "city",
            "administrative_exists": True,
            "monitoring_available": True,
            "location_docs": [],
            "stations": [],
            "cities": [area],
        }

    # ------------------------------------------------------------------------
    # Neither LGD nor MongoDB recognizes the area.
    # ------------------------------------------------------------------------

    raise ApiError(
        "unknown_area",
        (
            f"'{area}' is not a valid district/city "
            f"for '{matching_state}'"
        ),
        404,
    )


# ============================================================================
# AQI / FORECAST RECORD FILTER
# ============================================================================

def area_record_filter(
    resolved: dict,
) -> dict:
    """
    Build a MongoDB filter selecting AQI/forecast records
    for a resolved area.
    """

    ors: list[dict] = []

    # ------------------------------------------------------------------------
    # Station-based filtering
    # ------------------------------------------------------------------------

    if resolved["stations"]:

        ors.append(
            {
                "station_id": {
                    "$in": resolved["stations"]
                }
            }
        )

    # ------------------------------------------------------------------------
    # City-based filtering
    # ------------------------------------------------------------------------

    if resolved["cities"]:

        ors.append(
            {
                "city": {
                    "$in": resolved["cities"]
                }
            }
        )

    # ------------------------------------------------------------------------
    # State filter
    # ------------------------------------------------------------------------

    f: dict = {
        "state": resolved["state"]
    }

    # ------------------------------------------------------------------------
    # Add area filters when available
    # ------------------------------------------------------------------------

    if ors:

        f["$or"] = ors

    return f


# ============================================================================
# MONITORING COVERAGE
# ============================================================================

def coverage(
    resolved: dict,
) -> dict:
    """
    Return actual AQI monitoring coverage from MongoDB.

    This function does NOT use LGD to invent coverage.

    For a valid LGD district without monitoring records, coverage will
    correctly report zero stations/cities and no historical records.
    """

    docs = resolved.get(
        "location_docs",
        [],
    )

    # ------------------------------------------------------------------------
    # Historical start dates
    # ------------------------------------------------------------------------

    starts = [
        d["history_start"]
        for d in docs
        if d.get("history_start")
    ]

    # ------------------------------------------------------------------------
    # Historical end dates
    # ------------------------------------------------------------------------

    ends = [
        d["history_end"]
        for d in docs
        if d.get("history_end")
    ]

    # ------------------------------------------------------------------------
    # Return coverage information
    # ------------------------------------------------------------------------

    return {
        "matched_level": resolved["matched_level"],

        "administrative_exists": resolved.get(
            "administrative_exists",
            True,
        ),

        "monitoring_available": resolved.get(
            "monitoring_available",
            bool(docs),
        ),

        "n_stations": len(
            resolved.get(
                "stations",
                [],
            )
        ),

        "n_cities": len(
            resolved.get(
                "cities",
                [],
            )
        ),

        "history_start": (
            min(starts)
            if starts
            else None
        ),

        "history_end": (
            max(ends)
            if ends
            else None
        ),

        "total_records": sum(
            int(
                d.get(
                    "n_records",
                    0,
                )
            )
            for d in docs
        ),
    }