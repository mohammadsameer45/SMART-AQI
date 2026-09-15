"""Pytest fixtures for SMART AQI backend tests.

These are integration tests: they run against the local MongoDB seeded by
`scripts/seed_database.py`. If that DB is missing, the API tests are skipped.

Auth is Clerk-only (see backend/utils/auth.py) - there is no local JWT to
mint for tests. `auth_headers` instead mints a *real* Clerk session token via
Clerk's own Backend API (create a test user once per test run, then a fresh
session + session token per test), so `require_auth` is exercised exactly as
it verifies a real frontend-obtained token - no test-mode bypass.
"""
from __future__ import annotations

import uuid

import pytest

from backend.app import create_app
from backend.config import config
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


@pytest.fixture(scope="session")
def clerk_client():
    if not config.CLERK_SECRET_KEY:
        pytest.skip("CLERK_SECRET_KEY not set - cannot mint real Clerk test sessions")
    from clerk_backend_api import Clerk
    return Clerk(bearer_auth=config.CLERK_SECRET_KEY)


@pytest.fixture(scope="session")
def clerk_test_user(clerk_client):
    """One real Clerk user for the whole test run - created via Clerk's own
    Backend API, not our app (there is no local user store to write to)."""
    email = f"pytest-{uuid.uuid4().hex[:10]}@example.com"
    try:
        user = clerk_client.users.create(
            email_address=[email], password="Str0ng#Pass1-Test",
            skip_password_checks=True, first_name="Py", last_name="Test")
    except Exception as e:                              # noqa: BLE001
        # An invalid/unreachable CLERK_SECRET_KEY (e.g. a fork PR without
        # repo secrets) should skip these tests, not error the whole run -
        # require_auth itself is untouched, this only guards the fixture.
        pytest.skip(f"could not create a Clerk test user: {e}")
    yield user
    clerk_client.users.delete(user_id=user.id)


@pytest.fixture()
def auth_headers(seeded, clerk_client, clerk_test_user):
    if not seeded:
        pytest.skip("local smart_aqi DB not seeded")
    # A fresh session + token per test avoids Clerk's short-lived (~60s)
    # session tokens expiring mid-suite.
    session = clerk_client.sessions.create(request={"user_id": clerk_test_user.id})
    token = clerk_client.sessions.create_token(session_id=session.id).jwt
    return {"Authorization": f"Bearer {token}"}
