"""Auth endpoint: GET /api/auth/me.

Sign-in and sign-up happen entirely client-side against Clerk
(useSignIn/useSignUp in the React app) - Flask never sees a password. This
blueprint only verifies the resulting Clerk session token (require_auth,
backend/utils/auth.py) and exposes the matching profile.
"""
from __future__ import annotations

from flask import Blueprint, g

from backend.services import auth_service
from backend.utils.auth import require_auth
from backend.utils.responses import ok

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.get("/me")
@require_auth
def me():
    return ok(auth_service.me(g.user["id"]))
