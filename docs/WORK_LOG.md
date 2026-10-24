# Work Log

Every implementation session records: date, branch, exact commands, results, skipped checks, limitations, and manual prerequisites. Never claim completion based only on HTTP 200 or a green mocked test.

## 2026-10-23 — Configurable private-LAN web binding

- **Branch:** `FIX/configurable-lan-bind`
- **What:** Made the web bind address configurable while preserving loopback as the default. Documented binding to a specific server LAN address with firewall access restricted to the authorized client, since the current app has no user authentication.
- **Commands:**
  - `git checkout -b FIX/configurable-lan-bind` → passed.
  - `git diff --check` → passed.
  - Server: updated the Compose bind address to `192.168.1.104`, then recreated the web service with `CALIPER_WEB_BIND=192.168.1.104 CALIPER_WEB_PORT=8080 docker compose up -d --force-recreate web` → user confirmed access from the other laptop works.
- **Skipped / limitations:** Docker Compose startup and LAN reachability were not exercised from this environment; host firewall configuration is OS-specific.
- **Manual prerequisites:** Set `CALIPER_WEB_BIND` to the server's LAN IPv4 address, restrict inbound web-port access to the client IPv4 address, then recreate the web service.

## 2026-10-23 — Complete project CRUD in the workspace UI

- **Branch:** `feature/project-crud-ui`
- **What:** Added fresh project details, server-confirmed editing, and confirmed deletion to the projects UI. Updates are reflected only after a successful PUT and fresh GET; deletions are reflected only after DELETE succeeds and a fresh list omits the project. Added accessible confirmation/error states and UI behavior coverage.
- **Commands and results:**
  - `git checkout -b feature/project-crud-ui` → passed.
  - `pnpm.cmd exec vitest run src/App.test.tsx --pool=forks --maxWorkers=1 --minWorkers=1 --reporter=verbose` → 5 passed.
  - `pnpm.cmd run build` → passed (TypeScript check and Vite production build).
  - `git diff --check` → passed.
- **Backend baseline:** `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run pytest` → 5 passed, 3 PostgreSQL integration tests skipped because no isolated PostgreSQL test database is configured. `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff check src tests migrations` → passed.
- **Skipped / limitations:** UI tests use a mocked HTTP API. The PostgreSQL integration cases require the isolated test database and were not run in this Windows environment.
- **Manual prerequisites:** Run the deployed Docker build on the Linux host after the branch is delivered there.

## 2026-10-23 — Docker frontend build permission

- **Branch:** `FIX/pnpm-workspace-docker-build`
- **What:** Copy `pnpm-workspace.yaml` into the frontend build image before `pnpm install`, so pnpm 11 reads the repository's explicit `esbuild` build permission.
- **Commands:**
  - `git checkout -b FIX/pnpm-workspace-docker-build` → passed.
  - `docker compose build web` → not run locally; Docker Linux engine is unavailable in this environment. The user's Linux build failed at `pnpm install` with `ERR_PNPM_IGNORED_BUILDS` for `esbuild` before this correction.
- **Skipped / limitations:** The corrected Docker image still needs to be built on a host with a working Docker engine.
- **Manual prerequisites:** Fetch/checkout this branch on the Linux server, then rerun `docker compose up --build -d`.

---

## 2026-10-23 — Foundation bootstrap

- **Branch:** `main` → `feature/workspace-bootstrap`
- **What:** Initialized git repository; committed the foundation proposal (manifest, decisions, graph, principles, docs) as the root commit; added `.gitignore`, `AGENTS.md`, and this work log.
- **Commands:**
  - `git init -b main`
  - `git add -A && git commit -m "chore: caliper v2 foundation proposal (manifest, decisions, graph, principles)"`
  - `git checkout -b feature/workspace-bootstrap`
- **Result:** Repository initialized; foundation files tracked.
- **Skipped / limitations:** No runtime code yet. Backend/frontend framework, ORM, migration tool, package manager, and job system are still `undecided_record_before_implementation` in the manifest and require explicit approval per IMPLEMENTATION_RULES_FOR_AI rule 2.
- **Manual prerequisites:** Owner approval of proposed decisions D-011+ before implementation begins.

## 2026-10-23 — Architecture approval

- **Branch:** `feature/workspace-bootstrap`
- **What:** Owner authorized implementation of all proposed decisions and the full project scope. Recorded D-001 through D-016 as Accepted; selected the recorded API, persistence, frontend, package-management, and job-runner stack in the manifest.
- **Commands:**
  - `git status --short --branch`
  - `git branch --show-current`
  - `git diff --stat`
  - `python --version`
  - `uv --version`
  - `node --version`
  - `pnpm.cmd --version` → `11.25.0`
  - `docker version --format '{{.Client.Version}} / {{.Server.Version}}'` → Docker client `29.7.2`; daemon unavailable (Linux engine named pipe missing)
- **Result:** Decisions recorded as Accepted. Work remains on the existing feature branch; pre-existing decision-file edits were preserved and included in the approved decision record. pnpm is available.
- **Skipped / limitations:** Docker Compose verification is blocked until Docker Desktop's Linux engine is running. No application code or release gates have been verified yet.
- **Manual prerequisites:** None for beginning the implementation; Docker availability may affect local integration verification.

## 2026-10-23 — Projects vertical slice

- **Branch:** `feature/workspace-bootstrap`
- **What:** Added a FastAPI project API with Clean Architecture boundaries, async SQLAlchemy/psycopg persistence, Alembic migration, PostgreSQL CRUD integration tests, a React/Vite/Tailwind/shadcn-style projects workspace, server-confirmed project creation, health/readiness routes, Compose services, and setup/backup documentation. The web service binds to loopback; database credentials are injected through environment variables and are not committed.
- **Commands and results:**
  - `uv lock` → lockfile generated.
  - `uv sync --frozen` → installed the locked Python dependencies, including SQLAlchemy async support.
  - `uv run ruff format src tests migrations` → completed; final pass left all 18 Python files unchanged.
  - `uv run ruff check src tests migrations` → passed.
  - `uv run pytest` → 5 passed; 3 PostgreSQL integration tests skipped because no test database was available. Starlette emitted a TestClient/httpx deprecation warning.
  - `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv run alembic upgrade head --sql` → generated PostgreSQL DDL offline; migration was not applied to a server.
  - `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv run python -c "from caliper.main import app; assert app.docs_url == '/api/docs'; assert app.openapi_url == '/api/openapi.json'"` → API import and documentation routes verified.
  - `pnpm.cmd install --lockfile-only` → frontend lockfile generated/updated.
  - `pnpm.cmd install --frozen-lockfile` → passed; esbuild build permission recorded in `pnpm-workspace.yaml`.
  - `pnpm.cmd test` → 2 UI behavior tests passed.
  - `pnpm.cmd run build` → TypeScript check and Vite production build passed.
  - `$env:POSTGRES_PASSWORD='caliper-compose-validation'; docker compose config --quiet` → passed using a dummy validation value.
  - `git diff --check` → passed.
- **Environment:** Docker CLI 29.7.2 and Compose v5.5.1 are installed. `docker version --format '{{.Client.Version}} / {{.Server.Version}}'` reports that the Docker Linux engine pipe is missing. No PostgreSQL server command is available.
- **Skipped / limitations:** Real PostgreSQL CRUD, migration application, app/database startup, Docker image build, persistence after container restart, and backup/restore execution remain unverified until a Docker engine or isolated PostgreSQL test service is available. The local slice has no authentication; Compose binds the UI to `127.0.0.1` and does not publish the API port.
- **Manual prerequisites:** Start/provide a Docker Linux engine, then run `docker compose --profile test run --build --rm integration-tests`, `docker compose up --build -d`, and the persistence/restart and backup/restore checks documented in README.

## 2026-10-24 — Single administrator authentication and HTTPS gateway

- **Branch:** `feature/single-admin-auth` (based on `feature/project-crud-ui`)
- **What:** Recorded owner-approved D-017. Added an interactive administrator bootstrap/password-rotation CLI, Argon2id hashes, PostgreSQL-backed revocable session hashes, protected project routes, Secure/HttpOnly/SameSite=Strict cookies, a sign-in screen, and a Caddy internal-CA HTTPS gateway. Documented LAN access and Windows certificate trust. Graph responsibilities and edges were updated; node statuses remain planned until the full release gates are verified.
- **Commands and results:**
  - `uv --cache-dir <writable-cache> add "pwdlib[argon2]"` → added pwdlib 0.3.1 and locked Argon2 dependencies.
  - `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → passed, 6 UI tests.
  - `pnpm.cmd run build` → passed (TypeScript and Vite production build).
  - `uv --cache-dir <writable-cache> run pytest` → 6 passed, 4 PostgreSQL integration tests skipped because no test database was configured.
  - `uv --cache-dir <writable-cache> run ruff check --fix src tests migrations`; `uv ... run ruff format src tests migrations`; `uv ... run ruff check src tests migrations` → formatting and lint passed.
  - `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv --cache-dir <writable-cache> run alembic upgrade head --sql` → generated PostgreSQL DDL for both migrations without connecting to or changing a database.
  - `uv --cache-dir <writable-cache> run python -m caliper.cli --help` → CLI help works without database configuration.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `git diff --check` → passed before final review.
- **Skipped / limitations:** Docker Desktop's Linux engine is unavailable (`docker info` cannot connect to `dockerDesktopLinuxEngine`). Therefore PostgreSQL migration application, live login/session revocation, container image build, Caddy certificate issuance, browser trust, and LAN end-to-end access were not verified. PostgreSQL integration cases remain required before claiming this slice fully verified.
- **Manual prerequisites:** Start Docker on the target Linux server, rebuild Compose, initialize the administrator interactively, export Caddy's local root certificate to each Windows client, then complete the PostgreSQL integration and HTTPS login checks in README. No push or deployment was performed.

## 2026-10-24 — Encrypted secret-store foundation

- **Branch:** `feature/secret-store` (based on the committed `feature/single-admin-auth` slice)
- **What:** Accepted D-018, added an application secret-store port and Fernet file adapter, separate encrypted-data/keyring Compose volumes, first-run fail-closed keyring initialization, interrupted-rotation-safe key rollover, and a key rotation CLI command. Documented key-loss, backup, recovery, and rotation behavior.
- **Commands and results:**
  - `uv --cache-dir <writable-cache> add "cryptography>=44,<51"` → installed and locked `cryptography==50.0.2`.
  - `uv --cache-dir <writable-cache> run ruff check src tests migrations` → passed.
  - `uv --cache-dir <writable-cache> run pytest --basetemp=<writable-temp>` → 10 passed, 4 PostgreSQL integration tests skipped because no test database is configured.
  - Secret-store tests cover encrypted bytes, restart reads, destruction, key rotation, and fail-closed behavior after key loss.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `git diff --check` → passed before final review.
- **Skipped / limitations:** Docker remains unavailable locally. Compose init ordering, volume permissions, encrypted-file persistence, and key rotation need container verification. Credential API/UI and repository sync are not implemented in this foundation step.
- **Manual prerequisites:** Back up both named secret volumes and keep the keyring backup separately protected. Never delete a keyring while encrypted records exist.

## 2026-10-24 — Project credential lifecycle

- **Branch:** `feature/secret-store`
- **What:** Added project-scoped HTTPS token references and metadata, encrypted token storage, add/list/replace/disable/delete endpoints and UI, retryable cleanup/deletion state, project-deletion protection, and a bounded Git remote check. Tokens are never returned from API responses. A successful remote check reports `reachable`; public repositories may not prove token identity. SSH credentials remain deferred until a trusted host-key source is available.
- **Commands and results:**
  - `uv --cache-dir <writable-cache> run ruff check --fix src tests migrations`; `uv ... run ruff format src tests migrations`; `uv ... run ruff check src tests migrations` → passed.
  - `uv --cache-dir <writable-cache> run pytest --basetemp=<writable-temp>` → 13 passed; 5 PostgreSQL integration tests skipped without a test database.
  - `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 8 passed.
  - `pnpm.cmd run build` → passed.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv ... run alembic upgrade head --sql` → generated PostgreSQL DDL through migration 0003 without applying it.
  - `git diff --check` → passed before final review.
- **Skipped / limitations:** Docker engine unavailable, so the real PostgreSQL lifecycle/redaction integration test, DB migration application, live token check, and volume-backed secret deletion were not exercised. Full acceptance requires the Linux test profile.
- **Manual prerequisites:** Add an HTTPS repository and a read-only token, then use “Check access”. Treat `reachable` as connectivity evidence, not an identity proof for public repositories.

## 2026-10-24 — Repository knowledge synchronization

- **Branch:** `feature/repository-sync` (based on the committed `feature/secret-store` branch).
- **What:** Added protected repository sync/status/knowledge APIs, PostgreSQL migration `0004`, a bounded temporary Git clone and safe knowledge snapshot adapter, credential redaction, opt-in restricted local repositories, strict SSH host-key configuration, a UI sync/status/file viewer, and unit/UI/PostgreSQL integration coverage. Failed refreshes retain the last good snapshot and report stale.
- **Commands and results:**
  - From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff format src tests migrations` → passed.
  - From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff check src tests migrations` → passed.
  - From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run pytest --basetemp=C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\pytest-tmp` → 15 passed; 6 PostgreSQL integration tests skipped without an isolated PostgreSQL database. The new temporary bare Git repository and URL-safety tests passed.
  - From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 9 passed.
  - From `web/`, `pnpm.cmd run build` → passed (TypeScript and Vite production build).
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `$env:CALIPER_DATABASE_URL='postgresql+psycopg://test:test@localhost/caliper_test'; uv ... run alembic upgrade head --sql` → generated PostgreSQL DDL through `0004_repository_knowledge_sync` without connecting to a database.
  - With `CALIPER_DATABASE_URL` set to a disposable `caliper_test` URL, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run python -c "from caliper.main import app; print('\\n'.join(path for path in app.openapi()['paths'] if '/sync' in path or '/knowledge' in path))"` → both sync and knowledge paths appeared in OpenAPI.
  - `git diff --check` → passed.
- **Skipped / limitations:** Docker engine unavailable. PostgreSQL migrations and the new durable sync integration test, Docker build/startup, persistent restart behavior, and live remote access were not exercised. Sync currently occupies the bounded API request; D-015's persistent background worker remains a release blocker. Full details are in [task report 006](reports/006-repository-knowledge-sync.md).
- **Manual prerequisites:** Start Docker on the Linux server and run the isolated PostgreSQL integration profile before accepting repository sync as production-ready. Set `CALIPER_ALLOW_LOCAL_REPOSITORIES=true` only when local repository access is intentionally needed; populate `config/ssh/known_hosts` with host keys verified through a trusted source for SSH remotes.

## 2026-10-24 — PostgreSQL-backed background task runner

- **Branch:** `feature/durable-task-runner` (based on committed `feature/repository-sync`, commit `ad9b947`).
- **What:** Implements accepted D-015 for repository sync: PostgreSQL-persisted queue records, one advisory-lock-protected in-process worker, `FOR UPDATE SKIP LOCKED` task claims, bounded queue and retry count, restart requeue/reconciliation, 202 API acceptance, and UI status polling. Queue records contain project and credential IDs only. Project deletion remains blocked during queued/running sync.
- **Commands and results:**
  - From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run ruff check src tests migrations` → passed.
  - From `backend/`, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run pytest --basetemp=C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\pytest-tmp` → 17 passed; 6 PostgreSQL integration tests skipped without an isolated PostgreSQL test database.
  - From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 9 passed.
  - From `web/`, `pnpm.cmd run build` → passed (TypeScript and Vite production build).
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - With `CALIPER_DATABASE_URL` set to a disposable `caliper_test` URL, `uv --cache-dir C:\Users\Mohamed\.codex\visualizations\2026\10\23\01a16a05-9b43-73d2-b711-440fbac014a4\uv-cache run alembic upgrade head --sql` → generated DDL through migration `0005_durable_task_runner` without connecting to PostgreSQL.
  - `git diff --check` → passed before final commit review.
- **Skipped / limitations:** The Linux Docker engine is unavailable here; the real PostgreSQL queue, failure/restart recovery, applied migration, and container startup checks require the documented test profile on the Linux host.
- **Manual prerequisites:** Run the isolated `db-test` integration profile before treating the durable worker gate as verified.

## 2026-10-24 — Revisioned Principles Workspace

- **Branch:** `feature/principles-workspace` (based on committed `feature/durable-task-runner`, `5af6a20`).
- **What:** Added an authenticated workspace read model over persisted repository snapshots, safe Markdown views for Principles and Manifest, decision cards, search and snapshot navigation, and an accessible keyboard-operable graph from the synchronized `graph.yaml`. Graph references are validated server-side and errors are exposed to the view. Repository, branch, revision, last successful sync, and stale/sync status remain visible.
- **Commands and results:**
  - From `backend/`, `uv run pytest --basetemp=<writable-temp>` → 22 passed; 6 PostgreSQL integration tests skipped without isolated PostgreSQL.
  - From `backend/`, `uv run ruff check src tests migrations`; `uv run ruff format --check src tests migrations` → passed.
  - From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 10 passed.
  - From `web/`, `pnpm.cmd run build` → passed.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - With `CALIPER_DATABASE_URL` set to a disposable `caliper_test` URL, `uv run alembic upgrade head --sql` → generated PostgreSQL DDL through `0005_durable_task_runner`; no database connection was made.
  - FastAPI OpenAPI inspection → workspace endpoint registered.
  - Canonical `.caliper/graph.yaml` validation → no errors; `git diff --check` → passed.
- **Skipped / limitations:** Docker engine is unavailable. The API snapshot integration case and all other PostgreSQL cases remain skipped; no live API/UI/Docker run was performed. Graph nodes remain planned pending full release-gate verification.
- **Final backend note:** After the recorded 22-pass run, the workspace endpoint was changed to fetch project, sync state, and snapshot documents in one PostgreSQL statement to prevent mixed revisions during concurrent synchronization. Graph structure validation was also hardened. Ruff/format checks passed afterward. A pytest rerun was rejected by the approval prompt, so those final backend changes and their newly added unit/integration tests are not test-verified in this environment.
- **Manual prerequisites:** Run the isolated PostgreSQL integration profile on a Docker Linux host to verify the authenticated workspace endpoint against a persisted repository snapshot.

## 2026-10-24 — Ollama endpoint and model discovery

- **Branch:** `feature/ollama-provider` (based on committed `feature/principles-workspace`, `f4d228c`).
- **What:** Added administrator-protected Ollama endpoint configuration, bounded HTTP discovery of model identifiers, durable PostgreSQL settings and discovered-model selection, plus an administrator UI. Endpoint changes clear stale catalog/selection. This slice does not implement provider-account login, OpenCode, or inference. Updated README and graph descriptions; graph nodes remain planned until acceptance gates pass.
- **Commands and results:**
  - Backend focused tests (with writable `UV_CACHE_DIR`): `uv run --project backend pytest -q backend/tests/test_ollama_discovery.py backend/tests/test_ollama_provider_application.py` → 10 passed.
  - Backend quality: `uv run --project backend ruff check backend/src backend/tests backend/migrations`; `uv run --project backend ruff format --check backend/src backend/tests backend/migrations` → passed; 57 files already formatted.
  - From `web/`, `pnpm.cmd test -- --run --pool=forks --maxWorkers=1 --minWorkers=1` → 11 passed.
  - From `web/`, `pnpm.cmd run build` → passed (TypeScript and Vite production build).
  - From `backend/`, with a disposable `caliper_test` URL, `uv run alembic upgrade head --sql` → generated PostgreSQL DDL through `0006_ollama_provider`; this did not connect to or mutate a database.
  - FastAPI OpenAPI inspection → `/api/providers/ollama`, `/api/providers/ollama/validate`, and `/api/providers/ollama/model` registered.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `git diff --check` → passed before final commit review.
- **Skipped / limitations:** Docker Linux engine is unavailable; the new persistence integration case, applied migration, full backend suite, container startup, live Ollama reachability, and browser flow were not exercised. Inference and provider-account login are outside this slice.
- **Manual prerequisites:** On the Linux host, run the isolated PostgreSQL integration profile and validate against a reachable Ollama endpoint before marking the graph node complete.

## 2026-10-24 — Encrypted backup and guarded restore tooling

- **Branch:** `feature/backup-restore` (based on `feature/ollama-provider` at `19ef70f`).
- **What:** Added maintenance-only Compose volume access and Bash backup/restore scripts. The backup stops if API writes are active, creates a PostgreSQL custom dump and separate secret-data/keyring archives, encrypts each file with GnuPG AES-256, and restricts local file modes. Restore checks the exact Compose project, requires the database running and API/secret-init stopped, decrypts and checks all inputs before mutations, and requires typing the project-specific confirmation phrase. README covers passphrase separation and excluded `.env`/Caddy state.
- **Commands and results:**
  - `bash -n scripts/backup.sh scripts/restore.sh` → passed using Git Bash after sandbox IPC restrictions prevented its first in-sandbox launch.
  - `$env:POSTGRES_PASSWORD='compose-validation-only'; docker compose config --quiet` → passed.
  - `git diff --check` → passed before final review.
- **Skipped / limitations:** Docker's Linux engine is unavailable on this workstation, and GnuPG is not installed here. Backup/restore execution, encrypted-volume archive operation, database replacement, and recovery/restart behavior were not run. Cross-store restore is not atomic; if interrupted, keep the API stopped and rerun the same complete bundle before resuming service. This acceptance gate remains open pending a Linux host restore drill.
- **Manual prerequisites:** Install GnuPG on the Linux server, stop API writes, create a backup on encrypted storage, then restore only into the intended Compose project and verify administrator login, projects, and credentials. Keep keyring backup and passphrase separate from the other artifacts.

## 2026-10-24 — Runtime acceptance and encrypted restore drill

- **Branch:** `FIX/docker-apt-https` (based on the accepted backup/restore work).
- **What:** Fixed the Docker build's Debian HTTPS package source, mounted backend tests and canonical graph data into the integration-test container, excluded frontend build/dependency output from its Docker context, flushed a newly enqueued task before inserting its foreign-key dependent sync row, and enabled Pydantic validation from knowledge-document dataclasses.
- **Commands and results:**
  - `docker compose --profile test run --build --rm integration-tests` → **41 passed**, 2 warnings, against the isolated PostgreSQL test database.
  - Docker API and web image builds → passed; frontend tests → **11 passed**; `pnpm.cmd run build` → passed; backend Ruff check and format check → passed (57 files already formatted).
  - Isolated `caliper-acceptance` Compose startup → PostgreSQL/API/web healthy; `/health/live` and `/health/ready` returned their distinct expected states.
  - Authenticated project create/read/update/list via the live HTTPS API → passed. Recreated only the API container; it became healthy and returned the updated record from a fresh PostgreSQL read.
  - `scripts/backup.sh` and `scripts/restore.sh` → passed against the isolated Compose project using GnuPG with separate temporary test passphrases. Deleted the acceptance record, restored the encrypted database and both secret volumes, restarted the API, then verified administrator login and a fresh read of the restored record.
  - `$env:POSTGRES_PASSWORD='<test-only value>'; docker compose -p caliper-acceptance down` → removed acceptance containers/network without `-v`; named test volumes remain isolated and preserved. Temporary encrypted artifacts and passphrase files were removed.
  - `git diff --check` → passed.
- **Skipped / limitations:** A clean clone build and browser-driven end-to-end suite were not run. No live Ollama endpoint was available. Provider-login and OpenCode CLI integration remain unimplemented; these release gates must pass before the project plan is complete. Production LAN deployment was not changed. Architecture graph nodes remain `planned` until each responsibility has its required direct verification.
- **Manual prerequisites:** None for the isolated PostgreSQL, runtime restart, or backup/restore checks recorded here. The remaining model-provider and browser end-to-end gates still need implementation and verification.

## 2026-10-24 — OpenCode provider authentication and model selection

- **Branch:** `feature/opencode-cli` (based on runtime acceptance commit `903cda9`).
- **What:** Added the pinned OpenCode CLI runtime, in-memory runtime profile directory, encrypted profile reference and durable model selection, administrator-protected API-key/OAuth/disconnect endpoints, sanitized provider/model catalog, and an administrator UI. Accepted D-020, updated the architecture graph descriptions, added migration `0007_opencode_provider`, and documented provider login and storage boundaries.
- **Commands and results:**
  - `docker compose --profile test run --build --rm integration-tests` → **47 passed**, 2 warnings, against the isolated PostgreSQL test database. The suite exercised the actual OpenCode CLI server, persisted an acceptance-only invalid API key through the encrypted Secret Store, selected a catalog model and read it back, disconnected, and confirmed the secret was absent from encrypted payload bytes.
  - From `web/`, `pnpm.cmd test -- --pool=forks --maxWorkers=1 --minWorkers=1` → **13 passed**; `pnpm.cmd run build` → passed.
  - From `backend/`, `uv run ruff check src tests migrations`; `uv run ruff format --check src tests migrations` → passed (66 files formatted).
  - `$env:POSTGRES_PASSWORD='<ephemeral validation value>'; docker compose config --quiet` → passed. The temporary value is omitted from this log and was not committed.
  - `docker compose build api web` → both images built successfully, including the pinned OpenCode binary and frontend production bundle.
  - An isolated Compose runtime on loopback port `18443` → database/API/web healthy; `/health/live`, `/health/ready`, and OpenCode `/global/health` returned success; HTTPS web root returned HTTP 200. The isolated Compose project and its test volumes were removed after the run.
  - `git diff --check` → passed.
- **Skipped / limitations:** No real provider account, API credential, or OAuth consent was used. OAuth initiation and code/automatic callback behavior are wired to OpenCode's documented interface; completion against an account remains an administrator action. Model inference is outside this slice. The critical browser-driven end-to-end gate and other remaining unchecked acceptance criteria remain open; see `docs/INITIAL_ACCEPTANCE_CRITERIA.md` and [report 011](reports/011-opencode-provider.md).
- **Manual prerequisites:** Sign into a selected provider from **AI providers** before inference workflows can use it. The runtime is an administrator-controlled outbound connection.

## 2026-10-24 — Acceptance evidence for remote credentials and knowledge sync

- **Branch:** `feature/opencode-cli` (follow-up verification on top of `9f51e86`).
- **What:** Added PostgreSQL API coverage proving a credential stays `configured` until a remote validator confirms reachability, and asserted repository URL, branch, revision, attempt/success times, snapshot refresh, stale failure retention, and invalid graph-reference reporting in a controlled local bare-repository synchronization. Updated only the acceptance items supported by these database and UI test results.
- **Commands and results:**
  - `docker compose --profile test run --build --rm integration-tests` → **48 passed**, 2 warnings; the new and existing cases ran against PostgreSQL and an isolated local Git remote.
  - `git diff --check` → passed.
- **Skipped / limitations:** The entire browser-driven end-to-end gate and clean-checkout reproducibility gate have not yet been run. No live Ollama endpoint is configured; Ollama adapter validation/discovery is covered by focused adapter and PostgreSQL API tests using a controlled discovery response.
- **Manual prerequisites:** A live Ollama endpoint is needed to verify network reachability against a real Ollama installation.

## 2026-10-24 — Clean-checkout reproducibility

- **Branch:** `feature/opencode-cli`, clean clone at commit `8e1883a`.
- **What:** Cloned the committed feature branch into a fresh temporary directory with no working-tree state or preinstalled project dependencies. This verifies the accepted source tree rather than the active checkout.
- **Commands and results:**
  - `git clone --no-hardlinks --single-branch --branch feature/opencode-cli <workspace> <temporary-clean-checkout>` → passed; clone HEAD was `8e1883a105ca82455a594661f1a16cf9203bd786`, and the checkout was clean.
  - From the clean checkout, `docker compose build api web` → both images built successfully. The frontend lockfile passed its supply-chain policy check, dependencies installed from scratch, and the production TypeScript/Vite build passed.
  - Updated the clean-checkout acceptance gate to passed based on this build.
- **Skipped / limitations:** The clone verification covers container builds for the API and web services; it does not claim that user-specific server `.env` or LAN/firewall configuration can be reproduced from the repository.
- **Manual prerequisites:** None for the source build. Set server-local Compose environment values on each host as described in the README.

## 2026-10-24 — Browser acceptance and HTTPS proxy handling

- **Branch:** `feature/opencode-cli`.
- **What:** Added a disposable Playwright workflow that starts a uniquely named Docker Compose stack with random administrator/database credentials, seeds and verifies the administrator through stdin, checks browser sign-in and PostgreSQL-backed project creation, and removes only its own containers, network, and volumes. Added Playwright Chromium setup and ignored its generated reports. Enabled Uvicorn proxy-header handling for the private Compose reverse-proxy path; this fixes origin validation for HTTPS requests forwarded by Caddy.
- **Commands and results:**
  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/e2e.ps1` → **1 passed**; login, project create, persisted success notice and project rendering verified, then the isolated stack and volumes were removed.
  - `docker compose --profile test run --build --rm integration-tests` → **48 passed**, 2 warnings (previously recorded above).
  - `docker compose build api web` → passed for the clean checkout (previously recorded above).
  - `pnpm.cmd test` → **13 passed** across 5 frontend suites; Vitest excludes the dedicated Playwright directory.
  - `pnpm.cmd run build` → TypeScript and Vite production build passed.
  - `docker compose --profile test run --build --rm integration-tests` → **48 passed**, 2 warnings (previously recorded above).
  - `git diff --check` → passed.
- **Skipped / limitations:** The provider settings panel remained unresponsive in a browser-driven attempt even after 120 seconds, so it is not part of the passing browser scenario; OpenCode credential/model operations are verified by the PostgreSQL integration suite and provider controls by frontend tests. A temporary Ollama Docker image pull did not finish in the available time; the attempt was interrupted before a test container or live endpoint was created. No real provider account/credential was used. The remaining acceptance gate is live Ollama network/model discovery.
- **Manual prerequisites:** Configure a reachable Ollama endpoint to complete its live network/model-discovery gate; authorize a real provider account to verify external OAuth/API access.

## 2026-10-24 — Per-project AI model selection

- **Branch:** `feature/project-model-selection` (based on `feature/opencode-cli`).
- **What:** Added a project-owned PostgreSQL model assignment, authenticated API endpoints that offer models only from connected OpenCode providers or the latest successful Ollama discovery, and a project details control for selecting/clearing the assignment. Added accepted decision D-021, graph responsibility, migration `0008_project_model`, UI coverage, and PostgreSQL API coverage. This is model configuration only; inference remains out of scope.
- **Commands and results:**
  - `pnpm.cmd test -- --pool=forks --maxWorkers=1 --minWorkers=1` → **14 passed** across 6 suites, including project model save/read UI behavior.
  - `pnpm.cmd run build` → passed (TypeScript and Vite production build).
  - `uv run ruff check src tests migrations` → passed.
  - `uv run ruff format --check src tests migrations` → passed (70 files formatted).
  - `CALIPER_DATABASE_URL=postgresql+psycopg://caliper:offline-validation@localhost/caliper_test uv run alembic upgrade head --sql` → passed; generated migration chain through `0008_project_model` without connecting to a database.
  - `git diff --check` → passed.
- **Skipped / limitations:** The local Docker Linux engine is unavailable. The PostgreSQL API persistence test and real migration application could not run here; they are required before marking the acceptance criterion passed. The running host does not receive this feature until the branch is published and its API/web images are rebuilt.
- **Manual prerequisites:** Configure and connect an OpenCode provider or validate Ollama discovery before assigning a project model.
