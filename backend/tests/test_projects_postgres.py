import asyncio
import os
import subprocess
import time
from pathlib import Path

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
    assert (
        client.post(
            "/api/projects",
            json={"name": "X", "repository_url": "https://example.com/repo?token=sensitive-value"},
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


def test_repository_knowledge_sync_refreshes_and_preserves_last_snapshot(
    client: TestClient, tmp_path: Path, monkeypatch
):
    def git(cwd: Path, *arguments: str) -> None:
        subprocess.run(["git", *arguments], cwd=cwd, check=True, capture_output=True)

    source = tmp_path / "working"
    source.mkdir()
    git(source, "init", "--initial-branch=main")
    git(source, "config", "user.email", "test@example.invalid")
    git(source, "config", "user.name", "Caliper test")
    docs = source / "docs"
    docs.mkdir()
    guide = docs / "guide.md"
    guide.write_text("First version", encoding="utf-8")
    caliper = source / ".caliper"
    caliper.mkdir()
    (caliper / "graph.yaml").write_text(
        "nodes:\n  - {id: api, label: API}\nedges:\n  - {from: api, to: missing, relation: calls}\n",
        encoding="utf-8",
    )
    git(source, "add", ".")
    git(source, "commit", "-m", "first knowledge")
    local_root = tmp_path / "local-repositories"
    local_root.mkdir()
    bare = local_root / "controlled.git"
    git(tmp_path, "clone", "--bare", str(source), str(bare))
    monkeypatch.setenv("CALIPER_ALLOW_LOCAL_REPOSITORIES", "true")
    monkeypatch.setenv("CALIPER_LOCAL_REPOSITORY_ROOT", str(local_root))
    monkeypatch.setenv("CALIPER_REPOSITORY_ROOT", str(tmp_path / "sync-scratch"))

    project = client.post(
        "/api/projects",
        json={"name": "Knowledge", "repository_url": bare.as_uri(), "default_branch": "main"},
    )
    assert project.status_code == 201
    project_id = project.json()["id"]
    sync_url = f"/api/projects/{project_id}/sync"

    def wait_for_sync() -> dict:
        for _ in range(300):
            current = client.get(sync_url).json()
            if current["status"] not in {"queued", "running"}:
                return current
            time.sleep(0.05)
        pytest.fail("Repository sync task did not finish within 15 seconds")

    first = client.post(sync_url, json={})
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "queued"
    assert first.json()["task_id"]
    first_task_id = first.json()["task_id"]
    first_state = wait_for_sync()
    assert first_state["status"] == "synchronized"
    first_revision = first_state["revision"]
    database_url = (
        make_url(os.environ["TEST_DATABASE_URL"])
        if os.environ.get("TEST_DATABASE_URL")
        else database_url_from_environment()
    )
    sync_engine = create_engine(database_url)
    with sync_engine.connect() as connection:
        task = connection.execute(
            text("SELECT status, payload FROM tasks WHERE id = :task_id"),
            {"task_id": first_task_id},
        ).one()
    sync_engine.dispose()
    assert task.status == "succeeded"
    assert task.payload == {"project_id": project_id, "credential_id": None}
    assert client.get(sync_url).json()["revision"] == first_revision
    first_documents = client.get(f"/api/projects/{project_id}/knowledge").json()
    assert (
        next(document for document in first_documents if document["path"] == "docs/guide.md")[
            "content"
        ]
        == "First version"
    )
    workspace = client.get(f"/api/projects/{project_id}/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["sync"]["revision"] == first_revision
    assert {document["revision"] for document in workspace.json()["documents"]} == {first_revision}
    assert workspace.json()["graph"]["nodes"][0]["id"] == "api"
    assert "references unknown node(s): to" in workspace.json()["graph_errors"][0]

    guide.write_text("Second version", encoding="utf-8")
    git(source, "add", ".")
    git(source, "commit", "-m", "updated knowledge")
    git(source, "push", str(bare), "main")
    second = client.post(sync_url, json={})
    assert second.status_code == 202, second.text
    second_state = wait_for_sync()
    assert second_state["status"] == "synchronized"
    assert second_state["revision"] != first_revision
    second_documents = client.get(f"/api/projects/{project_id}/knowledge").json()
    assert (
        next(document for document in second_documents if document["path"] == "docs/guide.md")[
            "content"
        ]
        == "Second version"
    )

    assert (
        client.put(
            f"/api/projects/{project_id}",
            json={
                "name": "Knowledge",
                "repository_url": bare.as_uri(),
                "default_branch": "missing-branch",
            },
        ).status_code
        == 200
    )
    failed = client.post(sync_url, json={})
    assert failed.status_code == 202
    assert wait_for_sync()["status"] == "stale"
    fresh = client.get(sync_url).json()
    assert fresh["status"] == "stale"
    assert fresh["revision"] == second_state["revision"]
    stale_documents = client.get(f"/api/projects/{project_id}/knowledge").json()
    assert (
        next(document for document in stale_documents if document["path"] == "docs/guide.md")[
            "content"
        ]
        == "Second version"
    )


def test_ollama_configuration_validation_and_model_selection_are_persisted(
    client: TestClient, monkeypatch
):
    from caliper.adapters.ollama.discovery import OllamaHttpDiscoveryAdapter

    database_url = (
        make_url(os.environ["TEST_DATABASE_URL"])
        if os.environ.get("TEST_DATABASE_URL")
        else database_url_from_environment()
    )
    sync_engine = create_engine(database_url)
    with sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM ollama_settings"))

    async def discover(_self, _endpoint_url):
        return ["qwen:latest", "llama:8b"]

    monkeypatch.setattr(OllamaHttpDiscoveryAdapter, "discover", discover)
    try:
        initial = client.get("/api/providers/ollama")
        assert initial.status_code == 200
        assert initial.json()["status"] == "not_configured"

        configured = client.put(
            "/api/providers/ollama", json={"endpoint_url": "http://ollama:11434"}
        )
        assert configured.status_code == 200
        assert configured.json()["status"] == "configured"

        validated = client.post("/api/providers/ollama/validate")
        assert validated.status_code == 200
        assert validated.json()["status"] == "reachable"
        assert validated.json()["models"] == ["qwen:latest", "llama:8b"]
        assert validated.json()["checked_at"]

        selected = client.put("/api/providers/ollama/model", json={"model_id": "qwen:latest"})
        assert selected.status_code == 200
        assert selected.json()["selected_model_id"] == "qwen:latest"
        assert client.get("/api/providers/ollama").json()["selected_model_id"] == "qwen:latest"
        assert (
            client.put("/api/providers/ollama/model", json={"model_id": "unknown"}).status_code
            == 409
        )
    finally:
        with sync_engine.begin() as connection:
            connection.execute(text("DELETE FROM ollama_settings"))
        sync_engine.dispose()


def test_opencode_account_authentication_and_model_selection_are_durable(client: TestClient):
    from pathlib import Path

    response = client.get("/api/providers/opencode")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["version"]
    provider_id = next(
        provider_id
        for provider_id, methods in catalog["auth_methods"].items()
        if any(method.get("type") == "api" for method in methods)
    )
    provider = next(item for item in catalog["providers"] if item["id"] == provider_id)
    assert provider["models"]
    secret = "acceptance-only-invalid-key"
    connected = client.put(
        f"/api/providers/opencode/auth/{provider_id}/api-key",
        json={"api_key": secret, "metadata": {}},
    )
    assert connected.status_code == 200
    assert provider_id in connected.json()["connected_provider_ids"]
    assert secret not in connected.text

    model_id = provider["models"][0]["id"]
    selected = client.put(
        "/api/providers/opencode/model",
        json={"provider_id": provider_id, "model_id": model_id},
    )
    assert selected.status_code == 200
    fresh = client.get("/api/providers/opencode").json()
    assert fresh["selected_provider_id"] == provider_id
    assert fresh["selected_model_id"] == model_id

    database_engine = create_engine(
        make_url(os.environ["TEST_DATABASE_URL"])
        if os.environ.get("TEST_DATABASE_URL")
        else database_url_from_environment()
    )
    try:
        with database_engine.connect() as connection:
            secret_ref = connection.execute(
                text("SELECT auth_secret_ref FROM opencode_settings WHERE id = 1")
            ).scalar_one()
    finally:
        database_engine.dispose()
    assert secret_ref
    vault = Path(os.environ["CALIPER_SECRET_DATA_DIR"])
    encrypted = b"".join(path.read_bytes() for path in vault.iterdir() if path.is_file())
    assert secret.encode() not in encrypted

    disconnected = client.delete(f"/api/providers/opencode/auth/{provider_id}")
    assert disconnected.status_code == 200
    assert provider_id not in disconnected.json()["connected_provider_ids"]
    assert disconnected.json()["selected_model_id"] is None
    assert client.get("/api/providers/opencode").json()["selected_provider_id"] is None
