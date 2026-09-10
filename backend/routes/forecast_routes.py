"""7-day forecast endpoint."""
from __future__ import annotations

from flask import Blueprint, request

from backend.services import forecast_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("forecast", __name__, url_prefix="/api")


@bp.get("/aqi/forecast/<state>/<area>")
@require_auth
def forecast(state, area):
    model = request.args.get("model") or None
    return ok(forecast_service.forecast(state, area, model))
