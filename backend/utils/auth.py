"""Clerk session-token verification + the route auth decorator for SMART AQI.

Clerk is the sole identity provider. The frontend signs users in directly
against Clerk (useSignIn/useSignUp) and attaches the resulting session token
as `Authorization: Bearer <token>`. This module never issues its own token -
it only verifies Clerk's, via Clerk's own backend (network JWKS check), and
exposes the verified claims on flask.g.user exactly as the old JWT-based
decorator did, so no route file needs to change.
"""
from __future__ import annotations

import functools

from clerk_backend_api import AuthenticateRequestOptions, authenticate_request
from clerk_backend_api.security.types import AuthStatus
from flask import g, request

from backend.config import config
from backend.utils.responses import ApiError


def require_auth(fn):
    """Decorator: verifies the Clerk session token and puts the claims on
    flask.g.user = {"id": <clerk user id>, "email": <str or None>}."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        state = authenticate_request(
            request,
            AuthenticateRequestOptions(secret_key=config.CLERK_SECRET_KEY),
        )
        if state.status != AuthStatus.SIGNED_IN or not state.payload:
            raise ApiError("unauthorized",
                           "Authorization: Bearer <Clerk session token> required", 401)
        g.user = {"id": state.payload.get("sub"), "email": state.payload.get("email")}
        return fn(*args, **kwargs)
    return wrapper
