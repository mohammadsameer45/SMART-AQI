"""Auth flow + JWT/bcrypt unit tests."""
from __future__ import annotations

import uuid

import pytest

from backend.utils.auth import (decode_token, hash_password, make_token,
                                verify_password)
from backend.utils.responses import ApiError


def test_password_hash_roundtrip():
    h = hash_password("Str0ng#Pass1")
    assert h != "Str0ng#Pass1"
    assert verify_password("Str0ng#Pass1", h)
    assert not verify_password("wrong", h)


def test_token_roundtrip():
    tok = make_token("abc123", "a@b.com")
    claims = decode_token(tok)
    assert claims["sub"] == "abc123" and claims["email"] == "a@b.com"


def test_token_tampered_rejected():
    with pytest.raises(ApiError):
        decode_token(make_token("x", "y@z.com") + "junk")


@pytest.mark.parametrize("body,code", [
    ({"name": "A B", "email": "bad", "password": "Str0ng#1a",
      "confirm_password": "Str0ng#1a"}, "invalid_email"),
    ({"name": "A B", "email": "x@y.com", "password": "weak",
      "confirm_password": "weak"}, "weak_password"),
    ({"name": "A B", "email": "x@y.com", "password": "Str0ng#1a",
      "confirm_password": "different1A#"}, "password_mismatch"),
    ({"name": "1", "email": "x@y.com", "password": "Str0ng#1a",
      "confirm_password": "Str0ng#1a"}, "invalid_name"),
])
def test_register_validation(client, seeded, body, code):
    if not seeded:
        pytest.skip("db not seeded")
    r = client.post("/api/auth/register", json=body)
    assert r.status_code >= 400
    assert r.get_json()["error"]["code"] == code


def test_register_login_me(client, seeded):
    if not seeded:
        pytest.skip("db not seeded")
    email = f"pytest_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Str0ng#Pass1"
    r = client.post("/api/auth/register", json={
        "name": "Py Test", "email": email, "password": pw,
        "confirm_password": pw})
    assert r.status_code == 201
    assert client.post("/api/auth/register", json={
        "name": "Py Test", "email": email, "password": pw,
        "confirm_password": pw}).status_code == 409  # dup

    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200
    tok = r.get_json()["data"]["token"]

    assert client.post("/api/auth/login",
                       json={"email": email, "password": "nope"}).status_code == 401

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.get_json()["data"]["user"]["email"] == email

    from backend.models import mongo_models as M
    M.col(M.USERS).delete_one({"email": email})


def test_protected_requires_token(client):
    assert client.get("/api/states").status_code == 401
