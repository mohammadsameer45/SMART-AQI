"""Web Push subscription management for threshold alerts."""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.config import config
from backend.models import mongo_models as M
from backend.services import push_service
from backend.utils.auth import require_auth
from backend.utils.responses import ApiError, ok

bp = Blueprint("push", __name__, url_prefix="/api")


@bp.get("/push/vapid-public-key")
def vapid_public_key():
    return ok({"key": config.VAPID_PUBLIC_KEY, "configured": push_service.configured()})


@bp.post("/push/subscribe")
@require_auth
def subscribe():
    sub = request.get_json(silent=True) or {}
    if not sub.get("endpoint") or not sub.get("keys"):
        raise ApiError("bad_request", "Invalid push subscription", 400)
    now = M.utcnow()
    M.col(M.PUSH_SUBSCRIPTIONS).update_one(
        {"endpoint": sub["endpoint"]},
        {"$set": {"user_id": g.user["id"], "endpoint": sub["endpoint"],
                  "keys": sub["keys"], "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True)
    return ok({"subscribed": True}, status=201)


@bp.delete("/push/subscribe")
@require_auth
def unsubscribe():
    endpoint = (request.get_json(silent=True) or {}).get("endpoint")
    if not endpoint:
        raise ApiError("bad_request", "endpoint required", 400)
    M.col(M.PUSH_SUBSCRIPTIONS).delete_one(
        {"user_id": g.user["id"], "endpoint": endpoint})
    return ok({"unsubscribed": True})
