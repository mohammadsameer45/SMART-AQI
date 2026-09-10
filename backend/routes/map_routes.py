"""GeoJSON for the 3D India map (states) and per-state drill-down (districts)."""
from __future__ import annotations

from flask import Blueprint

from backend.services import map_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("map", __name__, url_prefix="/api/map")


@bp.get("/india")
@require_auth
def india():
    return ok(map_service.india())


@bp.get("/state/<state>")
@require_auth
def state(state):
    return ok(map_service.state(state))
