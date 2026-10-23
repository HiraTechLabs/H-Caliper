# Implementation report 001 — Projects vertical slice

**Date:** 2026-10-23
**Branch:** `feature/workspace-bootstrap`
**Status:** Implementation is present; release verification is pending Docker/PostgreSQL availability.

## Delivered

- Project create, list, read, update, and delete API routes using FastAPI and Pydantic.
- Framework-independent project rules and application use cases.
- Async SQLAlchemy 2.x adapter using psycopg 3, with an Alembic PostgreSQL migration.
- Real-PostgreSQL CRUD integration tests guarded to use only a database whose name includes `test`.
- React/Vite/TypeScript project workspace using Tailwind CSS and local shadcn/ui-style components.
- UI state comes from confirmed server responses; failed creates do not add local projects or show success.
- Liveness and PostgreSQL readiness routes.
- Docker Compose configuration with a persistent application database volume, health checks, non-root app/web containers, and an isolated ephemeral test database.
- Setup, PostgreSQL test, backup, and restore instructions in README.

## Verification

| Check | Result |
|---|---|
| Python lint (`uv run ruff check src tests migrations`) | Passed |
| Backend unit tests (`uv run pytest`) | 5 passed; one Starlette TestClient/httpx deprecation warning |
| PostgreSQL CRUD integration tests | 3 skipped: no PostgreSQL test server available |
| Alembic SQL generation (`uv run alembic upgrade head --sql`) | Passed offline; migration not applied |
| API import and OpenAPI route smoke check | Passed |
| UI behavior tests (`pnpm.cmd test`) | 2 passed |
| TypeScript and Vite build (`pnpm.cmd run build`) | Passed |
| Frozen pnpm install | Passed |
| Compose syntax/config (`docker compose config --quiet`) | Passed with a dummy local validation password |
| Docker build/start and persistence/restart | Not run; Docker Linux engine is unavailable |
| Backup/restore execution | Not run; Docker/PostgreSQL unavailable |

## Operational boundary

The first slice has no authentication. Compose publishes the web UI only on `127.0.0.1`; the API has no host port. Do not expose this slice on a shared or public network before an authenticated access layer is implemented.

## Next verification step

With a running Docker Linux engine, execute:

```powershell
docker compose --profile test run --build --rm integration-tests
docker compose up --build -d
```

Then verify project data survives API container recreation and exercise the documented backup/restore procedure. Later project slices remain gated on the release criteria in `docs/INITIAL_ACCEPTANCE_CRITERIA.md`.
