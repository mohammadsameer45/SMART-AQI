"""Consistent JSON envelope for every SMART AQI API response."""
from __future__ import annotations

from typing import Any

from flask import jsonify


def ok(data: Any = None, status: int = 200, **extra):
    body = {"ok": True, "data": data}
    if extra:
        body.update(extra)
    return jsonify(body), status


def err(code: str, message: str, status: int = 400, **extra):
    body = {"ok": False, "error": {"code": code, "message": message}}
    if extra:
        body["error"].update(extra)
    return jsonify(body), status


class ApiError(Exception):
    """Raise inside a route/service; the app error handler renders it."""

    def __init__(self, code: str, message: str, status: int = 400, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra
