"""JWT + bcrypt helpers and the route auth decorator for SMART AQI."""
from __future__ import annotations

import functools
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import g, request

from backend.config import config
from backend.utils.responses import ApiError


# --------------------------------------------------------------- passwords ----
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"),
                         bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ tokens ----
def make_token(user_id: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + timedelta(hours=config.JWT_EXPIRES_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET,
                          algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ApiError("token_expired", "Session expired, please log in again",
                       401)
    except jwt.InvalidTokenError:
        raise ApiError("invalid_token", "Invalid authentication token", 401)


def _bearer() -> str:
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise ApiError("no_token", "Authorization: Bearer <token> required", 401)
    return h[7:].strip()


def require_auth(fn):
    """Decorator: validates the JWT and puts the claims on flask.g.user."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        claims = decode_token(_bearer())
        g.user = {"id": claims["sub"], "email": claims.get("email")}
        return fn(*args, **kwargs)
    return wrapper
