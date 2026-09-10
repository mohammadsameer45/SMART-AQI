"""Weather endpoint (Open-Meteo, no API key)."""
from __future__ import annotations

from flask import Blueprint

from backend.services import weather as weather_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("weather", __name__, url_prefix="/api")


@bp.get("/weather/<state>/<area>")
@require_auth
def weather(state, area):
    return ok(weather_service.for_area(state, area))
