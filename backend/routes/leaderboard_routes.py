"""National AQI leaderboard + multi-area comparison."""
from __future__ import annotations

from flask import Blueprint, request

from backend.services import aqi_service, leaderboard_service
from backend.utils.auth import require_auth
from backend.utils.responses import ApiError, ok

bp = Blueprint("leaderboard", __name__, url_prefix="/api")

MIN_COMPARE, MAX_COMPARE = 2, 4


@bp.get("/leaderboard")
@require_auth
def leaderboard():
    return ok(leaderboard_service.leaderboard())


@bp.get("/compare")
@require_auth
def compare():
    raw = (request.args.get("areas") or "").strip()
    pairs = [p for p in raw.split(",") if p.strip()]
    if not (MIN_COMPARE <= len(pairs) <= MAX_COMPARE):
        raise ApiError("bad_request",
                       f"Provide {MIN_COMPARE}-{MAX_COMPARE} areas as "
                       "comma-separated 'State:Area' pairs.", 400)
    out = []
    for p in pairs:
        if ":" not in p:
            raise ApiError("bad_request", f"Invalid area '{p}', expected 'State:Area'.", 400)
        state, area = (s.strip() for s in p.split(":", 1))
        out.append({"state": state, "area": area,
                    "current": aqi_service.current(state, area)})
    return ok({"areas": out})
