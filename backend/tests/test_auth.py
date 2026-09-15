"""Auth flow tests - Clerk is the sole identity provider (see
backend/utils/auth.py). There is no local register/login/password to test;
`auth_headers` (conftest.py) mints a real Clerk session token, so these tests
exercise the real verification path, not a stub.
"""
from __future__ import annotations


def test_me_with_real_clerk_session(client, auth_headers):
    r = client.get("/api/auth/me", headers=auth_headers)
    assert r.status_code == 200, r.get_json()
    user = r.get_json()["data"]["user"]
    assert user["id"] and user["email"]
    assert user["name"]


def test_protected_requires_token(client):
    assert client.get("/api/states").status_code == 401


def test_invalid_token_rejected(client):
    r = client.get("/api/states", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
