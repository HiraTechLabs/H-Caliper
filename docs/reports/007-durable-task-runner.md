# Task report 007 — PostgreSQL-backed task runner

**Date:** 2026-10-24  
**Branch:** `feature/durable-task-runner` (based on `feature/repository-sync`)  
**Decision:** Implements the accepted D-015 single-process worker and durable task storage.

## Implemented

- Added migration `0005_durable_task_runner`, a PostgreSQL JSONB task table, and a task reference on each project's sync state. The persisted payload contains only the project ID and optional credential ID; token bytes remain in the encrypted secret store.
- Repository sync now returns `202 Accepted` after committing a queued task. The UI polls the persisted sync state, refreshes knowledge after completion, and reports timeout as still running rather than claiming success.
- Added one in-process worker guarded by a PostgreSQL advisory lock. It claims work with `FOR UPDATE SKIP LOCKED`, runs one job at a time, records completion/failure, and retries interrupted jobs on server restart up to three attempts.
- Bounded the waiting queue at 1,000 jobs and serializes admission while checking the limit. Only one active sync can exist per project, and project deletion stays blocked while work is queued or running.
- On restart, the worker re-queues interrupted tasks, reconciles a task whose sync already committed, and marks abandoned/over-retried work stale or failed while retaining the prior knowledge snapshot.
- Updated the PostgreSQL integration scenario to exercise 202 acceptance, persisted task state, successful refreshed knowledge, and stale-snapshot retention after a task failure.

## Verification

- From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff check src tests migrations` → passed.
- From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run pytest --basetemp=C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\pytest-tmp` → 17 passed, 6 PostgreSQL integration tests skipped because no isolated PostgreSQL test database was configured.
- From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 9 passed.
- From `web/`, `pnpm.cmd run build` → TypeScript and Vite production build passed.
- `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
- With `CALIPER_DATABASE_URL` set to a disposable `caliper_test` URL, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run alembic upgrade head --sql` → generated PostgreSQL DDL through migration `0005_durable_task_runner` without connecting to a database.
- With the same disposable URL configured, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run python -c "from caliper.main import app; print('\\n'.join(path for path in app.openapi()['paths'] if '/sync' in path or '/knowledge' in path))"` → sync and knowledge paths appeared in OpenAPI.
- `git diff --check` → passed.

## Not verified

- The local Docker Linux engine is unavailable, so migration application, worker/database integration, process restart recovery, and Compose startup have not been exercised in a live PostgreSQL container.
- The PostgreSQL integration test now covers a queued task, durable task record, successful document refresh, and stale-snapshot preservation, but that case was skipped locally. Restart requeue/reconciliation is implemented but has no live test result yet.
- No deployment or push was performed.
