import asyncio
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from caliper.adapters.postgres.connection import database_url_from_environment


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    url_text = os.environ.get("TEST_DATABASE_URL")
    if not url_text and not os.environ.get("CALIPER_DB_NAME"):
        pytest.skip(
            "Set TEST_DATABASE_URL or CALIPER_DB_* to the isolated caliper_test PostgreSQL database"
        )
    parsed_url = make_url(url_text) if url_text else database_url_from_environment()
    if parsed_url.get_backend_name() != "postgresql":
        pytest.fail("Persistence integration tests require PostgreSQL; SQLite is not supported")
    if "test" not in (parsed_url.database or "").lower():
        pytest.fail("Refusing integration tests unless the target database name includes 'test'")

    os.environ["CALIPER_DATABASE_URL"] = parsed_url.render_as_string(hide_password=False)
    config = Config("alembic.ini")
    command.upgrade(config, "head")

    from caliper.adapters.postgres.auth_repository import set_admin_password
    from caliper.adapters.postgres.database import SessionLocal, engine
    from caliper.adapters.secret_store.fernet_store import FernetFileSecretStore
    from caliper.application.auth import hash_password
    from caliper.main import app

    async def configure_test_admin():
        async with SessionLocal() as session:
            await set_admin_password(session, hash_password("integration-test-password"))
        await engine.dispose()

    asyncio.run(configure_test_admin())
    secret_root = tmp_path_factory.mktemp("caliper-secrets")
    os.environ["CALIPER_SECRET_DATA_DIR"] = str(secret_root / "vault")
    os.environ["CALIPER_SECRET_KEYRING"] = str(secret_root / "keys" / "keyring.json")
    FernetFileSecretStore(
        secret_root / "vault", secret_root / "keys" / "keyring.json"
    ).initialize_keyring()
    with TestClient(app, base_url="https://testserver") as test_client:
        login = test_client.post(
            "/api/auth/session", json={"password": "integration-test-password"}
        )
        assert login.status_code == 200
        yield test_client


@pytest.fixture(autouse=True)
def empty_projects_table(client: TestClient):
    url_text = os.environ.get("TEST_DATABASE_URL")
    if url_text or os.environ.get("CALIPER_DB_NAME"):
        url = make_url(url_text) if url_text else database_url_from_environment()
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM credentials"))
            connection.execute(text("DELETE FROM projects"))
        engine.dispose()
    if not client.get("/api/auth/session").json()["authenticated"]:
        login = client.post("/api/auth/session", json={"password": "integration-test-password"})
        assert login.status_code == 200
    yield


def test_project_crud_is_durable_and_fresh_read_matches(client: TestClient):
    created = client.post(
        "/api/projects",
        json={
            "name": "Caliper",
            "description": "Software factory",
            "default_branch": "main",
        },
    )
    assert created.status_code == 201
    body = created.json()
    project_id = body["id"]

    fetched = client.get(f"/api/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json() == body

    updated = client.put(
        f"/api/projects/{project_id}",
        json={
            "name": "Caliper Updated",
            "description": "Updated",
            "default_branch": "develop",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Caliper Updated"
    assert client.get("/api/projects").json()[0]["id"] == project_id

    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_project_validation_and_missing_delete(client: TestClient):
    assert client.post("/api/projects", json={"name": "   "}).status_code == 422
    assert (
        client.post(
            "/api/projects", json={"name": "X", "repository_url": "file:///tmp"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/projects",
            json={"name": "X", "repository_url": "https://user:token@example.com/repo"},
        ).status_code
        == 422
    )
    assert client.delete("/api/projects/00000000-0000-0000-0000-000000000000").status_code == 404


def test_liveness_and_postgres_readiness(client: TestClient):
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json() == {"status": "ready"}


def test_project_routes_require_admin_and_logout_revokes_session(client: TestClient):
    client.delete("/api/auth/session")
    assert client.get("/api/projects").status_code == 401
    login = client.post("/api/auth/session", json={"password": "integration-test-password"})
    assert login.status_code == 200
    assert "httponly" in login.headers["set-cookie"].lower()
    assert "secure" in login.headers["set-cookie"].lower()
    assert client.get("/api/projects").status_code == 200
    client.delete("/api/auth/session")
    assert client.get("/api/projects").status_code == 401


def test_credential_lifecycle_redacts_secret_and_blocks_project_delete(client: TestClient):
    project = client.post("/api/projects", json={"name": "Credential project"}).json()
    credential_url = f"/api/projects/{project['id']}/credentials"
    secret = "test-token-must-never-be-returned"

    created = client.post(
        credential_url,
        json={"name": "GitHub read token", "kind": "https_token", "secret": secret},
    )
    assert created.status_code == 201
    credential = created.json()
    credential_id = credential["id"]
    assert secret not in created.text
    assert credential["status"] == "configured"
    assert credential["enabled"] is True
    assert client.delete(f"/api/projects/{project['id']}").status_code == 409
    assert client.post(f"{credential_url}/{credential_id}/validate").status_code == 409

    listing = client.get(credential_url)
    assert listing.status_code == 200
    assert secret not in listing.text
    assert listing.json()[0]["id"] == credential_id

    replacement = client.put(
        f"{credential_url}/{credential_id}",
        json={"name": "GitHub read token", "secret": "replacement-test-token"},
    )
    assert replacement.status_code == 200
    assert replacement.json()["status"] == "configured"
    assert "replacement-test-token" not in replacement.text

    disabled = client.patch(f"{credential_url}/{credential_id}", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert client.get(credential_url).json()[0]["id"] == credential_id

    assert client.delete(f"{credential_url}/{credential_id}").status_code == 204
    assert client.get(credential_url).json() == []
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
