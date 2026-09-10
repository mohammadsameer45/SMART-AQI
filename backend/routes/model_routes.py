"""Model comparison + insights endpoints."""
from __future__ import annotations

from flask import Blueprint

from backend.services import model_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("models", __name__, url_prefix="/api")


@bp.get("/model-metrics")
@require_auth
def model_metrics():
    return ok(model_service.metrics())


@bp.get("/model-insights/<model>")
@require_auth
def model_insights(model):
    return ok(model_service.insights(model))
