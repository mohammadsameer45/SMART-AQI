"""Clerk-backed profile lookup for SMART AQI.

Clerk owns identity and credentials entirely (email/password + Google) - the
frontend signs in directly against Clerk. This service only maps an already
-verified Clerk user id (see backend/utils/auth.py) to the small profile
shape the frontend expects, by asking Clerk's own Backend API for the user's
name/email/created_at. No password, no local JWT, no MongoDB `users` write.
"""
from __future__ import annotations

from datetime import datetime, timezone

from clerk_backend_api import Clerk

from backend.config import config
from backend.utils.responses import ApiError

_clerk = Clerk(bearer_auth=config.CLERK_SECRET_KEY)


def _primary_email(user) -> str | None:
    addrs = user.email_addresses or []
    primary = next((a for a in addrs if a.id == user.primary_email_address_id), None)
    if primary:
        return primary.email_address
    return addrs[0].email_address if addrs else None


def _public(user) -> dict:
    name = " ".join(p for p in (user.first_name, user.last_name) if p)
    email = _primary_email(user)
    created_at = None
    if user.created_at:
        created_at = datetime.fromtimestamp(
            user.created_at / 1000, tz=timezone.utc).isoformat()
    return {"id": user.id, "name": name or email, "email": email,
            "created_at": created_at}


def me(user_id: str) -> dict:
    try:
        user = _clerk.users.get(user_id=user_id)
    except Exception:                                  # noqa: BLE001
        raise ApiError("user_not_found", "Account no longer exists", 404)
    if not user:
        raise ApiError("user_not_found", "Account no longer exists", 404)
    return {"user": _public(user)}
