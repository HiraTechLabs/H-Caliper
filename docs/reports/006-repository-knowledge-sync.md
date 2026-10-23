# Task report 006 — Repository knowledge synchronization

**Date:** 2026-10-24  
**Branch:** `feature/repository-sync` (based on `feature/secret-store`)  
**Scope:** authenticated project repository sync, safe derived knowledge snapshots, and UI browsing.

## Implemented

- Added PostgreSQL tables and Alembic migration `0004_repository_knowledge_sync` for project sync state and revisioned knowledge files.
- Added authenticated GET/POST sync APIs and a fresh knowledge read API.
- Added bounded shallow Git clone and archive processing. Only Markdown, MDX, YAML, TOML, and JSON under `.caliper/` and `docs/`, plus `README.md` and `AGENTS.md`, are indexed. Files are capped at 1 MiB, each snapshot at 10 MiB, the full tree at 64 MiB and 20,000 entries. Symlinks and unsupported paths are excluded.
- Credential values and common token/private-key patterns are redacted before content and hashes are persisted. The temporary clone is deleted after sync. HTTPS redirects remain disabled, subprocess output is suppressed, and SSH enforces strict host-key checks with an administrator-provisioned `known_hosts` file.
- Repository URLs reject embedded/query/fragment credentials. Only one sync may run per project; deletion is rejected while a sync is active, and project settings are rechecked under a row lock before the sync begins. Aggregate credential material used for redaction is capped at 16 MiB.
- Local `file://` repositories are opt-in and confined to the read-only mounted `local-repositories/` directory.
- Sync failure marks the state failed on first attempt or stale after a prior success; it retains the prior knowledge snapshot. The UI shows state and revision and renders file content as escaped plain text. A successful sync reloads the server state and documents automatically.
- Documented local repository setup and SSH host-key provisioning. Added Git and UI behavior tests plus a PostgreSQL integration case for content refresh and stale-snapshot retention.

## Verification

- `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff format src tests migrations` → passed.
- `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff check src tests migrations` → passed.
- `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run pytest --basetemp=C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\pytest-tmp` → 15 passed, 6 PostgreSQL integration cases skipped because no isolated PostgreSQL database was configured. The local Git adapter and URL-safety tests passed; the adapter test used a real temporary bare repository.
- From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 9 passed.
- From `web/`, `pnpm.cmd run build` → TypeScript and Vite production build passed.
- `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
- `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv ... run alembic upgrade head --sql` → generated PostgreSQL DDL through migration `0004_repository_knowledge_sync` without applying it.
- `git diff --check` → passed.
- `CALIPER_DATABASE_URL` pointed to disposable `caliper_test`; `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run alembic upgrade head --sql` → generated PostgreSQL DDL through migration `0004` without connecting to a database.
- With the same disposable database URL configured, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run python -c "from caliper.main import app; print('\\n'.join(path for path in app.openapi()['paths'] if '/sync' in path or '/knowledge' in path))"` → both sync and knowledge API paths appeared in OpenAPI.

## Not verified / remaining gate

- Docker Desktop's Linux engine is unavailable in this environment. The migration was not applied to PostgreSQL; the integration case for durable API sync and the two-sync update/failure workflow therefore remains skipped. Container build/startup and persistence across restart are not verified.
- Sync currently runs as a bounded API request (Git subprocess timeout: 120 seconds). Accepted decision D-015 calls for long Git operations to run through the PostgreSQL-persisted background task runner. That worker is not implemented yet, so this implementation does not close the durable-background-execution release gate and should not be described as production-complete.
- No live remote provider access or LAN deployment was attempted. No push, merge, or deployment was performed.
