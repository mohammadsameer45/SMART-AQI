"""Input validation helpers for SMART AQI routes."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from backend.utils.responses import ApiError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,60}$")


def require(body: dict | None, *fields: str) -> dict:
    if not isinstance(body, dict):
        raise ApiError("bad_request", "JSON body required", 400)
    missing = [f for f in fields if not str(body.get(f, "")).strip()]
    if missing:
        raise ApiError("bad_request",
                       f"Missing field(s): {', '.join(missing)}", 400)
    return body


def clean_email(v: str) -> str:
    v = str(v).strip().lower()
    if not _EMAIL_RE.match(v) or len(v) > 120:
        raise ApiError("invalid_email", "Enter a valid email address", 400)
    return v


def clean_name(v: str) -> str:
    v = " ".join(str(v).split())
    if not _NAME_RE.match(v):
        raise ApiError("invalid_name",
                       "Name must be 2-60 letters (spaces, . ' - allowed)", 400)
    return v


def check_password(v: str) -> str:
    v = str(v)
    if len(v) < 8 or len(v) > 128:
        raise ApiError("weak_password",
                       "Password must be 8-128 characters", 400)
    classes = sum(bool(re.search(p, v)) for p in
                  (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if classes < 3:
        raise ApiError("weak_password",
                       "Use at least 3 of: lowercase, uppercase, digit, symbol",
                       400)
    return v


def clean_str(v: Any, name: str, maxlen: int = 80) -> str:
    v = str(v or "").strip()
    if not v:
        raise ApiError("bad_request", f"{name} is required", 400)
    if len(v) > maxlen:
        raise ApiError("bad_request", f"{name} too long", 400)
    return v


def parse_date(v: str | None, name: str) -> datetime | None:
    if not v:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    raise ApiError("bad_request", f"{name} must be YYYY-MM-DD", 400)


def one_of(v: str | None, allowed: set[str], name: str, default: str) -> str:
    if v is None or v == "":
        return default
    if v not in allowed:
        raise ApiError("bad_request",
                       f"{name} must be one of {sorted(allowed)}", 400)
    return v
