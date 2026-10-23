import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from caliper.adapters.postgres.connection import database_url_from_environment


@pytest.fixture(scope="module")
def client():
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

    from caliper.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def empty_projects_table(client: TestClient):
    url_text = os.environ.get("TEST_DATABASE_URL")
    if url_text or os.environ.get("CALIPER_DB_NAME"):
        url = make_url(url_text) if url_text else database_url_from_environment()
        engine = create_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM projects"))
        engine.dispose()
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
    assert client.delete("/api/projects/00000000-0000-0000-0000-000000000000").status_code == 404


def test_liveness_and_postgres_readiness(client: TestClient):
    assert client.get("/health/live").json() == {"status": "live"}
    assert client.get("/health/ready").json() == {"status": "ready"}
