"""
User-defined AQI threshold alerts. A rule is (user, state, area, threshold);
`list_for_user` re-checks each rule against the same `aqi_service.current`
current-AQI lookup the rest of the app uses, so "triggered" always reflects
a real, freshly-computed reading — never a cached/guessed value.
"""
from __future__ import annotations

from bson import ObjectId
from bson.errors import InvalidId

from backend.models import mongo_models as M
from backend.services import aqi_service
from backend.utils.responses import ApiError

MAX_RULES_PER_USER = 10


def list_for_user(user_id: str) -> list[dict]:
    rules = list(M.col(M.ALERTS).find({"user_id": user_id}).sort("created_at", 1))
    out = []
    for r in rules:
        cur = aqi_service.current(r["state"], r["area"])
        aqi = cur.get("AQI") if cur.get("available") else None
        out.append({
            "id": str(r["_id"]),
            "state": r["state"], "area": r["area"], "threshold": r["threshold"],
            "created_at": r["created_at"].isoformat(),
            "current_aqi": aqi,
            "is_live": cur.get("is_live"),
            "triggered": aqi is not None and aqi >= r["threshold"],
        })
    return out


def create(user_id: str, state: str, area: str, threshold: int) -> dict:
    if not (0 < threshold <= 500):
        raise ApiError("bad_threshold", "Threshold must be between 1 and 500", 400)
    # Fail loudly if the area doesn't exist rather than saving a dead rule.
    from backend.services.location_service import resolve_area
    resolve_area(state, area)

    already = {"user_id": user_id, "state": state, "area": area}
    if (M.col(M.ALERTS).find_one(already) is None
            and M.col(M.ALERTS).count_documents({"user_id": user_id}) >= MAX_RULES_PER_USER):
        raise ApiError("too_many_rules", f"Limit of {MAX_RULES_PER_USER} alert rules", 400)

    now = M.utcnow()
    M.col(M.ALERTS).update_one(
        already,
        {"$setOnInsert": {**already, "created_at": now},
         "$set": {"threshold": int(threshold)}},
        upsert=True)
    row = M.col(M.ALERTS).find_one(already)
    return {"id": str(row["_id"]), "state": state, "area": area, "threshold": row["threshold"]}


def delete(user_id: str, rule_id: str) -> None:
    try:
        oid = ObjectId(rule_id)
    except InvalidId:
        raise ApiError("bad_id", "Invalid alert id", 400)
    res = M.col(M.ALERTS).delete_one({"_id": oid, "user_id": user_id})
    if res.deleted_count == 0:
        raise ApiError("not_found", "Alert rule not found", 404)


def check_and_notify_all() -> dict:
    """
    Evaluate every alert rule (all users) against a fresh current-AQI read
    and push-notify only on the edge — the transition from not-triggered to
    triggered — so a still-bad reading doesn't re-notify every cycle. Called
    from scripts/check_alerts.py, run periodically by refresh_worker.py.
    """
    from backend.services import push_service

    checked = notified = 0
    for r in M.col(M.ALERTS).find({}):
        checked += 1
        cur = aqi_service.current(r["state"], r["area"])
        aqi = cur.get("AQI") if cur.get("available") else None
        triggered = aqi is not None and aqi >= r["threshold"]
        was_triggered = bool(r.get("was_triggered"))

        if triggered and not was_triggered:
            sent = push_service.send_to_user(
                r["user_id"], "SMART AQI alert",
                f"AQI in {r['area']}, {r['state']} is {round(aqi)} — "
                f"above your alert threshold of {r['threshold']}.")
            if sent:
                notified += 1

        if triggered != was_triggered:
            M.col(M.ALERTS).update_one(
                {"_id": r["_id"]},
                {"$set": {"was_triggered": triggered,
                          **({"last_notified_at": M.utcnow()} if triggered and not was_triggered else {})}})
    return {"checked": checked, "notified": notified}
