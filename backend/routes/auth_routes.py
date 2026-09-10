"""Auth endpoints: /api/auth/register, /login, /me."""
from __future__ import annotations

from flask import Blueprint, g, request

from backend.services import auth_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    return ok(auth_service.register(request.get_json(silent=True)), 201)


@bp.post("/login")
def login():
    return ok(auth_service.login(request.get_json(silent=True)))


@bp.get("/me")
@require_auth
def me():
    return ok(auth_service.me(g.user["id"]))
