from __future__ import annotations

import os
import subprocess
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_ROOT = Path("/tmp/hcaliper-pytest")
_ROOT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_ROOT / 'app.db'}")
os.environ.setdefault("SECRET_KEY", "test-only-secret-key-0123456789abcdef012345")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault("ENV", "test")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("WORKSPACE_ROOT", str(_ROOT / "workspaces"))
os.environ.setdefault("ALLOWED_LOCAL_REPO_ROOTS", str(_ROOT / "fixtures"))
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "10000")
os.environ.setdefault("LOGIN_RATE_LIMIT_PER_MINUTE", "10000")

from app.core.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


TEST_ENGINE = create_async_engine(f"sqlite+aiosqlite:///{_ROOT / 'tests.db'}")
TEST_SESSIONS = async_sessionmaker(TEST_ENGINE, expire_on_commit=False, autoflush=False)
API = "/api/v1"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "SecureTestPass123"
MEMBER_PASSWORD = "MemberPassword123"


def unique_slug(prefix: str = "project") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get("hcaliper_csrf")
    return {"X-CSRF-Token": token} if token else {}


@asynccontextmanager
async def make_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


async def login(client: AsyncClient, email: str, password: str) -> dict:
    response = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json().get("csrf_token", "")
    return response.json()


async def create_user_via_api(client: AsyncClient, *, email: str, role: str = "OPERATOR") -> dict:
    response = await client.post(
        f"{API}/users",
        headers=csrf_headers(client),
        json={"email": email, "password": MEMBER_PASSWORD, "full_name": email.split("@")[0], "role": role},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_project_via_api(client: AsyncClient, *, name: str, **overrides) -> dict:
    response = await client.post(
        f"{API}/projects",
        headers=csrf_headers(client),
        json={"name": name, "slug": unique_slug(name.lower().replace(" ", "-")), **overrides},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_task_via_api(client: AsyncClient, project_id: str, *, title: str) -> dict:
    response = await client.post(
        f"{API}/tasks",
        headers=csrf_headers(client),
        json={"project_id": project_id, "title": title, "description": "A valid task request for API role checks."},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def setup_pipeline_project(client: AsyncClient, local_repo: Path) -> dict:
    provider_response = await client.post(
        f"{API}/providers",
        headers=csrf_headers(client),
        json={"name": f"Mock {uuid.uuid4().hex[:6]}", "type": "mock", "enabled": True},
    )
    assert provider_response.status_code == 201, provider_response.text
    provider = provider_response.json()
    model_response = await client.post(
        f"{API}/providers/{provider['id']}/models",
        headers=csrf_headers(client),
        json={"model_id": "mock-model"},
    )
    assert model_response.status_code == 201, model_response.text
    project = await create_project_via_api(
        client,
        name="Pipeline Fixture",
        repository_url=str(local_repo),
        default_branch="main",
    )
    defaults = {}
    for role in ("planning", "execution", "review", "documentation"):
        defaults[f"default_{role}_provider_id"] = provider["id"]
        defaults[f"default_{role}_model"] = "mock-model"
    response = await client.patch(
        f"{API}/projects/{project['id']}", headers=csrf_headers(client), json=defaults
    )
    assert response.status_code == 200, response.text
    return {"project": response.json(), "provider": provider}


async def _override_db():
    async with TEST_SESSIONS() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture(autouse=True)
async def fresh_database():
    async with TEST_ENGINE.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = _override_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "admin@example.com", "password": "SecureTestPass123", "full_name": "Test Admin"},
    )
    assert response.status_code == 200, response.text
    csrf = response.json().get("csrf_token")
    client.headers["X-CSRF-Token"] = csrf or ""
    return client


@pytest_asyncio.fixture
async def local_repo(tmp_path):
    root = _ROOT / "fixtures" / f"repo-{uuid.uuid4().hex[:8]}"
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "initial fixture"], cwd=root, check=True)
    yield root
    import shutil
    shutil.rmtree(root, ignore_errors=True)


@pytest_asyncio.fixture
async def project(admin_client: AsyncClient):
    response = await admin_client.post(
        "/api/v1/projects",
        json={"name": "Test Workspace", "slug": "test-workspace", "description": "API test workspace"},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest_asyncio.fixture(autouse=True)
async def clean_workspace():
    import shutil

    shutil.rmtree(_ROOT / "workspaces", ignore_errors=True)
    (_ROOT / "workspaces").mkdir(parents=True, exist_ok=True)
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def dispose_test_engine():
    yield
    await TEST_ENGINE.dispose()
