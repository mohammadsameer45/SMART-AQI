"""Pytest fixtures for SMART AQI backend tests.

These are integration tests: they run against the local MongoDB seeded by
`scripts/seed_database.py`. If that DB is missing, the API tests are skipped.
"""
from __future__ import annotations

import uuid

import pytest

from backend.app import create_app
from backend.models import mongo_models as M


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def seeded() -> bool:
    try:
        M.ping()
        return M.col(M.AQI_RECORDS).estimated_document_count() > 0
    except Exception:
        return False


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client, seeded):
    if not seeded:
        pytest.skip("local smart_aqi DB not seeded")
    email = f"pytest_{uuid.uuid4().hex[:8]}@example.com"
    pw = "Str0ng#Pass1"
    r = client.post("/api/auth/register", json={
        "name": "Py Test", "email": email,
        "password": pw, "confirm_password": pw})
    assert r.status_code == 201, r.get_json()
    token = r.get_json()["data"]["token"]
    yield {"Authorization": f"Bearer {token}"}
    M.col(M.USERS).delete_one({"email": email})
