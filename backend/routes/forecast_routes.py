"""Forecast endpoints: 7-day (+3-day as a slice of it), 24-hour, outdoor
planner and recovery estimate."""
from __future__ import annotations

from flask import Blueprint, request

from backend.services import forecast_insight_service as insight
from backend.services import forecast_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("forecast", __name__, url_prefix="/api")


@bp.get("/aqi/forecast/<state>/<area>")
@require_auth
def forecast(state, area):
    model = request.args.get("model") or None
    return ok(forecast_service.forecast(state, area, model))


@bp.get("/aqi/forecast-24h/<state>/<area>")
@require_auth
def forecast_24h(state, area):
    return ok(insight.forecast_24h(state, area))


@bp.get("/aqi/outdoor-planner/<state>/<area>")
@require_auth
def outdoor_planner(state, area):
    return ok(insight.outdoor_planner(state, area))


@bp.get("/aqi/recovery/<state>/<area>")
@require_auth
def recovery(state, area):
    return ok(insight.recovery_prediction(state, area))
