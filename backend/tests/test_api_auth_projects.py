from __future__ import annotations

from httpx import AsyncClient
import pytest

pytestmark = pytest.mark.asyncio


async def test_bootstrap_login_me_logout_and_duplicate_bootstrap(client: AsyncClient):
    status = await client.get("/api/v1/auth/bootstrap-status")
    assert status.status_code == 200
    assert status.json()["bootstrap_required"] is True

    created = await client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "root@example.com", "password": "StrongPass12345", "full_name": "Root"},
    )
    assert created.status_code == 200
    assert created.json()["user"]["role"] == "ADMIN"
    csrf = created.json()["csrf_token"]
    assert "hcaliper_session" in created.cookies
    client.headers["X-CSRF-Token"] = csrf

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "root@example.com"

    duplicate = await client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "another@example.com", "password": "StrongPass12345"},
    )
    assert duplicate.status_code == 409

    logout = await client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "root@example.com", "password": "StrongPass12345"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["id"] == created.json()["user"]["id"]


async def test_invalid_login_and_cookie_csrf_protection(client: AsyncClient):
    bootstrap = await client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "admin@example.com", "password": "StrongPass12345"},
    )
    assert bootstrap.status_code == 200
    client.headers.pop("X-CSRF-Token", None)
    failed = await client.post("/api/v1/notifications/read-all")
    assert failed.status_code == 403  # Cookie-authenticated mutation must pass CSRF first.
    client.headers["X-CSRF-Token"] = bootstrap.json()["csrf_token"]
    bad_password = await client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrong"}
    )
    assert bad_password.status_code == 401


async def test_project_creation_seeds_caliper_and_safe_environment_defaults(
    admin_client: AsyncClient,
):
    response = await admin_client.post(
        "/api/v1/projects",
        json={"name": "CALIPER Project", "slug": "caliper-project"},
    )
    assert response.status_code == 201, response.text
    project = response.json()
    docs = await admin_client.get(f"/api/v1/projects/{project['id']}/caliper")
    assert docs.status_code == 200
    assert len(docs.json()) == 12
    assert sorted(d["slot"] for d in docs.json()) == list(range(1, 13))
    environments = await admin_client.get(f"/api/v1/projects/{project['id']}/environments")
    assert environments.status_code == 200
    assert environments.json()[0]["kind"] == "DEVELOPMENT"


async def test_project_archival_is_soft_delete(admin_client: AsyncClient, project: dict):
    response = await admin_client.delete(f"/api/v1/projects/{project['id']}")
    assert response.status_code == 204
    detail = await admin_client.get(f"/api/v1/projects/{project['id']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "ARCHIVED"
