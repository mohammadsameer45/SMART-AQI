"""User registration / login for SMART AQI."""
from __future__ import annotations

from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from backend.models import mongo_models as M
from backend.utils.auth import hash_password, make_token, verify_password
from backend.utils.responses import ApiError
from backend.utils.validation import (check_password, clean_email, clean_name,
                                      require)


def _public(user: dict) -> dict:
    return {"id": str(user["_id"]), "name": user["name"],
            "email": user["email"],
            "created_at": user["created_at"].isoformat()
            if isinstance(user["created_at"], datetime) else user["created_at"]}


def register(body: dict) -> dict:
    require(body, "name", "email", "password", "confirm_password")
    name = clean_name(body["name"])
    email = clean_email(body["email"])
    if body["password"] != body["confirm_password"]:
        raise ApiError("password_mismatch", "Passwords do not match", 400)
    check_password(body["password"])

    doc = {"name": name, "email": email,
           "password_hash": hash_password(body["password"]),
           "created_at": datetime.now(timezone.utc)}
    try:
        res = M.col(M.USERS).insert_one(doc)
    except DuplicateKeyError:
        raise ApiError("email_taken", "An account with that email exists", 409)
    doc["_id"] = res.inserted_id
    token = make_token(res.inserted_id, email)
    return {"token": token, "user": _public(doc)}


def login(body: dict) -> dict:
    require(body, "email", "password")
    email = clean_email(body["email"])
    user = M.col(M.USERS).find_one({"email": email})
    if not user or not verify_password(body["password"], user["password_hash"]):
        raise ApiError("bad_credentials", "Incorrect email or password", 401)
    token = make_token(user["_id"], email)
    return {"token": token, "user": _public(user)}


def me(user_id: str) -> dict:
    from bson import ObjectId
    try:
        user = M.col(M.USERS).find_one({"_id": ObjectId(user_id)})
    except Exception:
        user = None
    if not user:
        raise ApiError("user_not_found", "Account no longer exists", 404)
    return {"user": _public(user)}
