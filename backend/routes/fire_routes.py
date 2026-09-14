"""Forest-fire detection and fire-impact endpoints (NASA FIRMS)."""
from __future__ import annotations

from flask import Blueprint, request

from backend.services import fire_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("fire", __name__, url_prefix="/api")


@bp.get("/fire-events/<state>/<area>")
@require_auth
def fire_events(state, area):
    radius = request.args.get("radius_km", type=int) or 200
    return ok(fire_service.detect_fires(state, area, radius_km=radius))


@bp.get("/fire-impact/<state>/<area>")
@require_auth
def fire_impact(state, area):
    radius = request.args.get("radius_km", type=int) or 200
    return ok(fire_service.fire_impact(state, area, radius_km=radius))


@bp.get("/smoke/<state>/<area>")
@require_auth
def smoke_forecast(state, area):
    radius = request.args.get("radius_km", type=int) or 200
    return ok(fire_service.smoke_forecast(state, area, radius_km=radius))
