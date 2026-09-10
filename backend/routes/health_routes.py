"""Health advisory endpoint."""
from __future__ import annotations

from flask import Blueprint

from backend.services import health_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.get("/health-advisory/<state>/<area>")
@require_auth
def advisory(state, area):
    return ok(health_service.advisory(state, area))
