# Task report 008 — Revisioned Principles Workspace

**Date:** 2026-10-24  
**Branch:** `feature/principles-workspace` (based on `feature/durable-task-runner`)  
**Decision:** Implements the accepted D-009 visual knowledge workspace for confirmed repository snapshots.

## Implemented

- Added an authenticated project workspace endpoint that reads sync state and snapshot documents from one PostgreSQL statement, then parses `graph.yaml` from that same revision.
- Added bounded `yaml.safe_load` graph validation with aliases disabled. The API reports malformed YAML, invalid node IDs, duplicate IDs, malformed edges, and references to missing nodes without echoing parser input; invalid graph structures are withheld from the renderer and diagnostics are capped.
- Added Principles, Manifest, Decisions, and Graph views. Markdown raw HTML is not enabled and the rendered tree is sanitized. Search filters the current view; decision sections are shown as cards; snapshot links navigate within available documents or open HTTPS URLs.
- Added an accessible SVG graph with keyboard-operable component nodes and a text list that exposes the same statuses without relying on color.
- Added repository, branch, revision, last successful sync, and status metadata. Synchronization uses the durable task API and retained stale snapshots are labeled stale.
- Updated the architecture graph, decision consequences, run guide, and this report. Architecture graph nodes remain `planned` pending complete release-gate verification.

## Verification

- From `backend/`, `uv run pytest --basetemp=C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\pytest-tmp` → last complete run before the snapshot-read refactor: 22 passed; 6 PostgreSQL integration tests skipped because no isolated PostgreSQL test database was available.
- After the snapshot-read refactor, additional graph-structure hardening, and their unit/integration tests were added, Ruff formatting and lint passed, but the requested pytest rerun was rejected by the approval prompt. Those final backend changes and newly added tests have not been executed.
- From `backend/`, `uv run ruff check src tests migrations` and `uv run ruff format src tests migrations` → passed after the last backend edits.
- From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 10 passed.
- From `web/`, `pnpm.cmd run build` → TypeScript and Vite production build passed.
- `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
- With `CALIPER_DATABASE_URL` set to a disposable `caliper_test` URL, `uv run alembic upgrade head --sql` → PostgreSQL DDL generated through `0005_durable_task_runner` without connecting to a database.
- With the same disposable URL, loading FastAPI OpenAPI confirmed `/api/projects/{project_id}/workspace` is registered.
- `git diff --check` → passed.
- Unit validation against the checked-in `.caliper/graph.yaml` found no invalid references. An API/PostgreSQL integration case for the revisioned graph response was added but skipped with the other PostgreSQL tests.

## Not verified

- The local Docker Linux engine is unavailable, so the new workspace endpoint has not been exercised against a live PostgreSQL snapshot and the Docker build/startup gates remain unverified.
- The browser UI was verified in component tests and a production build, not in a live browser against Docker.
- No merge, push, or deployment was performed.
