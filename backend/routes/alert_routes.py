"""User-defined AQI threshold alert rules."""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.services import alert_service
from backend.utils.auth import require_auth
from backend.utils.responses import ApiError, ok

bp = Blueprint("alerts", __name__, url_prefix="/api")


@bp.get("/alerts")
@require_auth
def list_alerts():
    return ok(alert_service.list_for_user(g.user["id"]))


@bp.post("/alerts")
@require_auth
def create_alert():
    body = request.get_json(silent=True) or {}
    state, area, threshold = body.get("state"), body.get("area"), body.get("threshold")
    if not state or not area or threshold is None:
        raise ApiError("bad_request", "state, area and threshold are required", 400)
    return ok(alert_service.create(g.user["id"], state, area, threshold), status=201)


@bp.delete("/alerts/<rule_id>")
@require_auth
def delete_alert(rule_id):
    alert_service.delete(g.user["id"], rule_id)
    return ok({"deleted": rule_id})
