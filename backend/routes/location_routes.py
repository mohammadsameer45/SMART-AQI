"""Geographic selectors: states, districts/cities, locations."""
from __future__ import annotations

from flask import Blueprint

from backend.models import mongo_models as M
from backend.services import location_service as loc
from backend.services import state_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("locations", __name__, url_prefix="/api")


@bp.get("/states")
@require_auth
def states():
    return ok(loc.list_states())


@bp.get("/states/<state>/districts")
@require_auth
def districts(state):
    return ok(loc.areas_for_state(state))


@bp.get("/states/<state>/overview")
@require_auth
def state_overview(state):
    return ok(state_service.overview(state))


@bp.get("/live/status")
@require_auth
def live_status():
    """Freshness of the scheduled CPCB live-feed refresh (scripts/refresh_worker.py)."""
    from datetime import datetime, timezone
    doc = M.col("meta").find_one({"_id": "live_refresh"}, {"_id": 0})
    if not doc:
        return ok({"available": False,
                   "reason": "The live-feed refresh worker has not run yet. "
                             "Start it with `python scripts/refresh_worker.py`."})
    fin = doc.get("finished_at")
    age_min = None
    if isinstance(fin, datetime):
        age_min = round((datetime.now(timezone.utc) - fin).total_seconds() / 60)
    return ok({"available": True, "age_minutes": age_min, **doc})


@bp.get("/districts/<state>/<area>/locations")
@require_auth
def locations(state, area):
    r = loc.resolve_area(state, area)
    return ok({"state": state, "area": area,
               "matched_level": r["matched_level"],
               "locations": r["location_docs"],
               "coverage": loc.coverage(r)})
