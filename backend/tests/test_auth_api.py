"""Authentication, bootstrap and CSRF behaviour through the real ASGI app."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

from conftest import (  # noqa: E402
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    API,
    csrf_headers,
    unique_slug,
)


async def test_bootstrap_status_to_bootstrap_me_logout(client):
    status = await client.get(f"{API}/auth/bootstrap-status")
    assert status.status_code == 200
    assert status.json()["bootstrap_required"] is True

    response = await client.post(
        f"{API}/auth/bootstrap",
        json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "full_name": "Initial Admin",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["role"] == "ADMIN"
    assert body["csrf_token"]
    assert body["csrf_token"] == client.cookies.get("hcaliper_csrf")

    me = await client.get(f"{API}/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == ADMIN_EMAIL

    status = await client.get(f"{API}/auth/bootstrap-status")
    assert status.json()["bootstrap_required"] is False

    # A cookie-authenticated mutation without the double-submit header is denied.
    blocked = await client.post(f"{API}/auth/logout")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "csrf_failed"

    logout = await client.post(f"{API}/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}

    me_after = await client.get(f"{API}/auth/me")
    assert me_after.status_code == 401


async def test_duplicate_bootstrap_and_invalid_credentials(admin_client, client):
    duplicate = await admin_client.post(
        f"{API}/auth/bootstrap",
        json={
            "email": "other@example.com",
            "password": "AnotherPassword123",
            "full_name": "Other",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "already_initialised"

    wrong_password = await client.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": "NotTheRightPassword1"},
    )
    assert wrong_password.status_code == 401

    unknown_user = await client.post(
        f"{API}/auth/login",
        json={"email": "nobody@example.com", "password": "SomePassword123"},
    )
    assert unknown_user.status_code == 401

    valid = await client.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert valid.status_code == 200
    assert valid.json()["csrf_token"]


async def test_cookie_auth_mutations_require_matching_csrf_header(admin_client):
    admin_client.headers.pop("X-CSRF-Token", None)
    payload = {
        "name": "CSRF Fixture Project",
        "slug": unique_slug("csrf"),
        "description": "Created only when the CSRF token matches.",
    }

    missing = await admin_client.post(f"{API}/projects", json=payload)
    assert missing.status_code == 403
    assert missing.json()["detail"]["code"] == "csrf_failed"

    mismatched = await admin_client.post(
        f"{API}/projects",
        headers={"X-CSRF-Token": "not-the-cookie-value"},
        json=payload,
    )
    assert mismatched.status_code == 403

    accepted = await admin_client.post(
        f"{API}/projects", headers=csrf_headers(admin_client), json=payload
    )
    assert accepted.status_code == 201, accepted.text


async def test_unauthenticated_requests_are_rejected(client):
    me = await client.get(f"{API}/auth/me")
    assert me.status_code == 401
    providers = await client.get(f"{API}/providers")
    assert providers.status_code == 401
    projects = await client.get(f"{API}/projects")
    assert projects.status_code == 401
