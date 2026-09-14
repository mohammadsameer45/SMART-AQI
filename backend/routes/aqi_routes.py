"""AQI endpoints: current, history, pollutants, plus the composite dashboard."""
from __future__ import annotations

from flask import Blueprint, request

from backend.services import (aqi_service, analyst_service, forecast_service,
                              health_service,
                              pollutant_insight_service as insight,
                              pollution_event_service as events,
                              weather as weather_service)
from backend.services.location_service import coverage, resolve_area
from backend.utils.auth import require_auth
from backend.utils.responses import ok
from backend.utils.validation import one_of, parse_date

bp = Blueprint("aqi", __name__, url_prefix="/api")


@bp.get("/aqi/current/<state>/<area>")
@require_auth
def current(state, area):
    return ok(aqi_service.current(state, area))


@bp.get("/aqi/history/<state>/<area>")
@require_auth
def history(state, area):
    frm = parse_date(request.args.get("from"), "from")
    to = parse_date(request.args.get("to"), "to")
    grain = one_of(request.args.get("grain"), {"day"}, "grain", "day")
    return ok(aqi_service.history(state, area, frm, to, grain))


@bp.get("/pollutants/<state>/<area>")
@require_auth
def pollutants(state, area):
    return ok(aqi_service.pollutants(state, area))


@bp.get("/pollutants/<state>/<area>/<pollutant>/why")
@require_auth
def pollutant_why(state, area, pollutant):
    return ok(insight.why_pollutant(state, area, pollutant))


@bp.get("/aqi/trend/<state>/<area>")
@require_auth
def aqi_trend(state, area):
    return ok(insight.trend(state, area))


@bp.get("/aqi/spike/<state>/<area>")
@require_auth
def aqi_spike(state, area):
    return ok(insight.spike_detection(state, area))


@bp.get("/aqi/explanation/<state>/<area>")
@require_auth
def aqi_explanation(state, area):
    return ok(insight.explanation(state, area))


@bp.get("/aqi/source-analysis/<state>/<area>")
@require_auth
def aqi_source_analysis(state, area):
    return ok(insight.source_analysis(state, area))


@bp.get("/aqi/impact/<state>/<area>")
@require_auth
def aqi_impact(state, area):
    return ok(insight.impact_breakdown(state, area))


@bp.get("/dispersion/<state>/<area>")
@require_auth
def dispersion(state, area):
    return ok(insight.dispersion(state, area))


@bp.get("/aqi/events/<state>/<area>")
@require_auth
def aqi_events(state, area):
    return ok(events.detect_events(state, area))


@bp.get("/aqi/events/<state>/<area>/<event_id>")
@require_auth
def aqi_event_detail(state, area, event_id):
    return ok(events.event_detail(state, area, event_id))


@bp.post("/aqi/why-change")
@require_auth
def aqi_why_change():
    body = request.get_json(silent=True) or {}
    state = body.get("state")
    area = body.get("area")
    if not state or not area:
        from backend.utils.responses import ApiError
        raise ApiError("missing_field", "'state' and 'area' are required", 400)
    return ok(insight.why_change(state, area, body.get("from"), body.get("to")))


@bp.post("/aqi/analyst")
@require_auth
def aqi_analyst():
    body = request.get_json(silent=True) or {}
    state = body.get("state")
    area = body.get("area")
    question = body.get("question")
    if not state or not area or not question:
        from backend.utils.responses import ApiError
        raise ApiError("missing_field", "'state', 'area' and 'question' are required", 400)
    return ok(analyst_service.ask(state, area, question))


@bp.get("/dashboard/<state>/<area>")
@require_auth
def dashboard(state, area):
    r = resolve_area(state, area)
    cur = aqi_service.current(state, area)
    hist = aqi_service.history(state, area, None, None, "day")
    series = hist["series"][-90:]
    return ok({
        "state": state, "area": area,
        "coverage": coverage(r),
        "current": cur,
        "history_90d": series,
        "forecast": forecast_service.forecast(state, area),
        "advisory": health_service.advisory(state, area),
        "weather": _safe(lambda: weather_service.for_area(state, area)),
        "live_refresh": _safe(_live_refresh),
    })


def _live_refresh():
    from datetime import datetime, timezone
    from backend.models import mongo_models as M
    doc = M.col("meta").find_one({"_id": "live_refresh"},
                                 {"_id": 0, "finished_at": 1, "ok": 1,
                                  "cpcb_live_stations": 1})
    if not doc or not isinstance(doc.get("finished_at"), datetime):
        return {"running": False}
    age = round((datetime.now(timezone.utc) - doc["finished_at"]).total_seconds() / 60)
    return {"running": True, "age_minutes": age, "ok": doc.get("ok"),
            "stations": doc.get("cpcb_live_stations")}


def _safe(fn):
    try:
        return fn()
    except Exception as e:                           # noqa: BLE001
        return {"available": False, "reason": str(e)}
