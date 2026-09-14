"""
MongoDB access layer for SMART AQI.

Owns the single MongoClient, the collection-name constants, index creation, and
small data-access helpers shared by the seed pipeline and the API services.
The request path is strictly React -> Flask -> this module -> MongoDB (local).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from pymongo import ASCENDING, MongoClient
from pymongo.errors import OperationFailure
from pymongo.collection import Collection
from pymongo.database import Database

from backend.config import config

# ----------------------------------------------------------------- collections
USERS = "users"
LOCATIONS = "locations"
AQI_RECORDS = "aqi_records"
LIVE_AQI = "live_aqi"
FORECAST_RECORDS = "forecast_records"
MODEL_METRICS = "model_metrics"
HEALTH_ADVISORIES = "health_advisories"
ALERTS = "alerts"
PUSH_SUBSCRIPTIONS = "push_subscriptions"

ALL_COLLECTIONS = [USERS, LOCATIONS, AQI_RECORDS, FORECAST_RECORDS,
                   MODEL_METRICS, HEALTH_ADVISORIES, ALERTS, PUSH_SUBSCRIPTIONS]

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000,
                              tz_aware=True, appname="smart-aqi")
    return _client


def get_db() -> Database:
    return get_client()[config.MONGO_DB]


def col(name: str) -> Collection:
    return get_db()[name]


def ping() -> str:
    """Raises if the server is unreachable; returns its version string."""
    return get_client().server_info()["version"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------- indexes
# station_id is present-but-null on city-level documents, so a plain `sparse`
# index still indexes those nulls and a unique one would collide. A partial
# index keyed only on string station_ids is the correct guard.
_STATION_ID_STRING = {"station_id": {"$type": "string"}}


def _safe_create(coll: Collection, keys, **opts) -> str:
    """create_index that tolerates a pre-existing index with different options."""
    try:
        return coll.create_index(keys, **opts)
    except OperationFailure:
        coll.drop_index(opts["name"])
        return coll.create_index(keys, **opts)


def ensure_indexes() -> dict[str, list[str]]:
    """Create every index the app relies on. Idempotent."""
    created: dict[str, list[str]] = {}

    created[USERS] = [
        col(USERS).create_index([("email", ASCENDING)], unique=True,
                                name="ux_email"),
        col(USERS).create_index([("created_at", ASCENDING)], name="ix_created"),
    ]

    created[LOCATIONS] = [
        col(LOCATIONS).create_index([("state", ASCENDING)], name="ix_state"),
        col(LOCATIONS).create_index(
            [("state", ASCENDING), ("district", ASCENDING)], name="ix_state_district"),
        col(LOCATIONS).create_index(
            [("state", ASCENDING), ("district", ASCENDING), ("city", ASCENDING)],
            name="ix_state_district_city"),
        col(LOCATIONS).create_index(
            [("state", ASCENDING), ("city", ASCENDING)], name="ix_state_city"),
        _safe_create(col(LOCATIONS), [("station_id", ASCENDING)], unique=True,
                     partialFilterExpression=_STATION_ID_STRING,
                     name="ux_station_id"),
        col(LOCATIONS).create_index([("level", ASCENDING)], name="ix_level"),
    ]

    created[AQI_RECORDS] = [
        col(AQI_RECORDS).create_index(
            [("state", ASCENDING), ("district", ASCENDING), ("ts", ASCENDING)],
            name="ix_state_district_ts"),
        col(AQI_RECORDS).create_index(
            [("state", ASCENDING), ("city", ASCENDING), ("ts", ASCENDING)],
            name="ix_state_city_ts"),
        _safe_create(col(AQI_RECORDS),
                     [("station_id", ASCENDING), ("ts", ASCENDING)],
                     name="ix_station_ts",
                     partialFilterExpression=_STATION_ID_STRING),
        col(AQI_RECORDS).create_index(
            [("level", ASCENDING), ("ts", ASCENDING)], name="ix_level_ts"),
        col(AQI_RECORDS).create_index([("ts", ASCENDING)], name="ix_ts"),
    ]

    created[FORECAST_RECORDS] = [
        col(FORECAST_RECORDS).create_index(
            [("state", ASCENDING), ("city", ASCENDING), ("generated_at", ASCENDING)],
            name="ix_state_city_generated"),
        col(FORECAST_RECORDS).create_index(
            [("station_id", ASCENDING), ("forecast_date", ASCENDING)],
            name="ix_station_forecastdate", sparse=True),
        col(FORECAST_RECORDS).create_index(
            [("model", ASCENDING), ("generated_at", ASCENDING)],
            name="ix_model_generated"),
    ]

    created[MODEL_METRICS] = [
        col(MODEL_METRICS).create_index([("model_name", ASCENDING)], name="ix_model"),
        col(MODEL_METRICS).create_index([("training_date", ASCENDING)], name="ix_trained"),
        col(MODEL_METRICS).create_index([("is_best", ASCENDING)], name="ix_is_best"),
    ]

    created[HEALTH_ADVISORIES] = [
        col(HEALTH_ADVISORIES).create_index(
            [("aqi_bucket", ASCENDING), ("audience", ASCENDING)],
            unique=True, name="ux_bucket_audience"),
    ]

    created[ALERTS] = [
        col(ALERTS).create_index([("user_id", ASCENDING)], name="ix_user"),
        col(ALERTS).create_index(
            [("user_id", ASCENDING), ("state", ASCENDING), ("area", ASCENDING)],
            unique=True, name="ux_user_state_area"),
    ]

    created[PUSH_SUBSCRIPTIONS] = [
        col(PUSH_SUBSCRIPTIONS).create_index([("user_id", ASCENDING)], name="ix_user"),
        col(PUSH_SUBSCRIPTIONS).create_index(
            [("endpoint", ASCENDING)], unique=True, name="ux_endpoint"),
    ]
    return created


# ----------------------------------------------------------- read-side helpers
def list_states() -> list[str]:
    return sorted(col(LOCATIONS).distinct("state", {"state": {"$ne": None}}))


def list_districts(state: str) -> list[str]:
    return sorted(d for d in col(LOCATIONS).distinct(
        "district", {"state": state}) if d)


def list_locations(state: str, district: Optional[str] = None) -> list[dict]:
    q: dict[str, Any] = {"state": state}
    if district:
        q["district"] = district
    return list(col(LOCATIONS).find(q, {"_id": 0}).sort("city", ASCENDING))


def latest_record(state: str, city: str,
                  level: str = "city") -> Optional[dict]:
    return col(AQI_RECORDS).find_one(
        {"state": state, "city": city, "level": level},
        sort=[("ts", -1)], projection={"_id": 0})


def history(state: str, city: str, level: str = "city",
            start: Optional[datetime] = None, end: Optional[datetime] = None,
            limit: int = 5000) -> list[dict]:
    q: dict[str, Any] = {"state": state, "city": city, "level": level}
    if start or end:
        q["ts"] = {}
        if start:
            q["ts"]["$gte"] = start
        if end:
            q["ts"]["$lte"] = end
    return list(col(AQI_RECORDS).find(q, {"_id": 0})
                .sort("ts", ASCENDING).limit(limit))
