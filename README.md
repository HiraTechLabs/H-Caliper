# H-Caliper

**AI-driven software production factory.** H-Caliper coordinates project-scoped planning, implementation, deterministic validation, independent review, documentation, and human-controlled release through one persistent workflow.

> Integrations are only considered verified when an actual connectivity/acceptance test has passed. The mock adapter is for development and tests; it is not evidence of a real AI provider connection.

## Capabilities

- Persistent PostgreSQL-backed task pipeline with recovery, bounded retries, cancellation, events, and artifacts.
- Dedicated Git branch/worktree per task. No automatic merge; authorized human approval is required.
- Twelve project CALIPER principles and an intentionally reserved 13th slot.
- Four configurable agent roles: Planning, Execution, Review, Documentation.
- Provider capability registry for chat, agent execution, tools, file editing, terminal, streaming, and model discovery.
- Deterministic secret/change-policy checks plus project-specific allowlisted quality gates.
- Authentication, global roles and project membership, encrypted provider/repository secrets, CSRF protection, audit records, and production guardrails.

## Architecture

| Component | Implementation |
| --- | --- |
| API | Python 3.12, FastAPI, Pydantic 2 |
| Persistence | PostgreSQL 16, SQLAlchemy 2 async, Alembic |
| Worker | PostgreSQL-polled persistent worker; no Redis/Celery requirement |
| UI | React 19, TypeScript, Vite, Tailwind CSS |
| Isolation | Git mirror and task/attempt-specific worktrees |
| Deployment | Docker Compose, nginx, PostgreSQL and workspace volumes |

See [architecture](docs/architecture.md), [security](docs/security.md), and [ADRs](docs/adr/).

## Quick start: Docker Compose

Requirements: Docker Engine with Compose plugin, Linux, and 4 GB+ RAM recommended. Defaults use UI port `8080`, API port `8001`, PostgreSQL port `5433` to avoid common existing host services.

```bash
cp .env.example .env
# Generate three independent values using a trusted Python environment:
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'  # SECRET_KEY
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'  # ENCRYPTION_KEY
python3 -c 'import secrets; print(secrets.token_hex(32))'  # POSTGRES_PASSWORD (URL-safe)
# Replace the three placeholders in .env with the generated values.
chmod 600 .env
docker compose up -d --build
docker compose ps
```

Open <http://localhost:8080> and create the first administrator. There is no default account or password. API readiness is <http://localhost:8080/health>; API docs are at `/api/docs` outside production mode.

1. Register a provider, run its health test, then discover/add actual model IDs.
2. Create a project, connect its HTTPS repository, and set model defaults for all four agent roles.
3. Configure validation commands for the repository’s stack.
4. Submit a task; inspect the plan, diff, gates, review, docs, and artifacts.
5. An administrator must approve a merge. Production deployment is separately disabled by default.

## Local development

Use Python 3.12+, Node 22+, and an isolated PostgreSQL database. Do not stop or replace unrelated host services.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
export ENV=development
export DATABASE_URL='postgresql+asyncpg://hcaliper:YOUR_DEV_PASSWORD@127.0.0.1:5433/hcaliper'
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
export WORKSPACE_ROOT="$PWD/workspaces"
export COOKIE_SECURE=false
cd backend
../.venv/bin/alembic upgrade head
../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Run the worker in another terminal with `cd backend && ../.venv/bin/python -m app.worker`. Run the UI with `cd frontend && npm ci && npm run dev`; Vite serves port `3001` and proxies to API `8002` by default.

## Tests/build

```bash
cd backend
../.venv/bin/python -m pytest -q
../.venv/bin/ruff check app tests --select F
../.venv/bin/python -m compileall -q app alembic
cd ../frontend
npm ci && npm run build
```

Backend tests use isolated SQLite and temporary Git repositories. They do not replace a PostgreSQL/container acceptance run or live provider verification. See [test status](docs/test-status.md).

## Providers

Registered adapters include FreeLLMAPI, LM Studio, generic OpenAI-compatible HTTP, Ollama, OpenCode CLI, Codex CLI, Antigravity CLI, and test-only Mock. CLI availability/auth depends on the host; the default Compose image does not install/authenticate those CLIs. See [provider guide](docs/providers.md). An adapter existing is not evidence that it is reachable.

## Security and operations

- Generate unique `SECRET_KEY`, Fernet `ENCRYPTION_KEY`, and database password. Losing the encryption key makes stored credentials unrecoverable.
- Run production with `COOKIE_SECURE=true` behind HTTPS. Keep Postgres/private API ports firewalled; Compose mappings should be changed for public production hosts.
- The Docker socket is not mounted by default. Adding it grants powerful host control.
- Worker commands and repository code are not a hardened hostile-code sandbox. Use dedicated isolated worker hosts, least privilege, resource limits, restricted egress, and carefully scoped local repo roots.
- Production is denied unless explicitly enabled/configured and approved. Never expose production credentials to agents.

## Documentation

- [User guide](docs/user-guide.md) · [Administrator guide](docs/administrator-guide.md)
- [API reference](docs/api.md) · [Provider guide](docs/providers.md)
- [Deployment](docs/deployment.md) · [Backup/restore](docs/backup-restore.md)
- [Security](docs/security.md) · [Known limitations/roadmap](docs/known-limitations.md)
- [Architecture](docs/architecture.md) · [CALIPER templates](docs/caliper/)
