# Caliper Architecture Decisions

Statuses: **Proposed**, **Accepted**, **Superseded**, **Rejected**. The project owner approved the complete proposed architecture and first-slice scope on 2026-10-23.

## D-001 — PostgreSQL for operational data
- **Status:** Accepted
- **Decision:** PostgreSQL is the primary operational store. Use versioned migrations, explicit transaction boundaries, constraints, indexes, backup/restore procedures, and PostgreSQL-backed integration tests.
- **Reason:** Reliable relationships and durable state for projects, tasks, approvals, model configuration, and execution history.
- **Consequences:** PostgreSQL is required in development and deployment. SQLite is not the production operational database.

## D-002 — Python backend
- **Status:** Accepted
- **Decision:** Use Python. Select the web framework, ORM/data-access approach, migration tool, and job system explicitly before implementation; do not infer these from the language choice.
- **Consequences:** Domain logic must remain independent of the web framework and persistence implementation.

## D-003 — shadcn/ui
- **Status:** Accepted
- **Decision:** Use shadcn/ui as the UI component system. Explicitly choose and document the frontend framework, build tool, package manager, and styling conventions.
- **Consequences:** Components must be accessible, consistent, maintainable, and testable.

## D-004 — Dockerized services
- **Status:** Accepted
- **Decision:** Containerize the application and required services, including PostgreSQL. Use documented Docker Compose workflows unless a later decision chooses another orchestrator.
- **Consequences:** Define health checks, persistent volumes, non-root runtime, configuration, secret injection, backup, restore, and upgrade processes.

## D-005 — Canonical project knowledge
- **Status:** Accepted
- **Decision:** Principles, decisions, manifest, and graph remain version-controlled project files. PostgreSQL may store sync metadata and derived indexes, but does not silently replace the files as source of truth.
- **Consequences:** Display repository, branch, revision, last successful sync, and current sync status.

## D-006 — Server-confirmed UI state
- **Status:** Accepted
- **Decision:** Mutations must return a truthful outcome and resulting state/version where appropriate. The UI updates after confirmed success without requiring manual page refresh. Optimistic updates require tested rollback behavior.
- **Consequences:** Test mutation, fresh read, UI state, and persistence separately.

## D-007 — Secret-store boundary
- **Status:** Accepted
- **Decision:** Store secret values behind a dedicated interface. PostgreSQL stores references and non-sensitive metadata. The initial implementation may use an encrypted persistent store if key management, permissions, backup, recovery, rotation, and deletion semantics are documented.
- **Consequences:** Reference deletion, disabling a credential, and destroying a secret are distinct operations.

## D-008 — Separate model adapters
- **Status:** Accepted
- **Decision:** Provider login, Ollama, and OpenCode use separate adapters behind a common internal capability contract. Unsupported capabilities must be explicit.
- **Consequences:** Each adapter has independent setup validation, status checks, error mapping, and tests.

## D-009 — Visual Principles Workspace
- **Status:** Accepted
- **Decision:** Render principles, manifest, decisions, and graph as a visual workspace sourced from canonical files.
- **Consequences:** Safe Markdown, search, cross-links, accessible graph navigation, revision display, and truthful sync status are acceptance criteria.

## D-010 — Truthful status semantics
- **Status:** Accepted
- **Decision:** Distinguish configured, validated, reachable, authenticated, synchronized, stale, succeeded, and failed. Every status must define what was checked and when.
- **Consequences:** Credential existence alone must not mean repository access is Ready. HTTP 200 alone must not mean a business operation succeeded.

---

# Accepted implementation choices

The project owner approved the full proposed architecture and first-slice scope on 2026-10-23. These decisions are accepted and may guide implementation.

## D-011 — API framework: FastAPI
- **Status:** Accepted
- **Decision:** Use FastAPI with Pydantic v2 for the API layer: request/response validation, automatic OpenAPI contract, async handlers, and explicit dependency injection at the composition boundary.
- **Reason:** Matches the fixed Python constraint; validation and stable transport contracts are first-class, which the acceptance criteria require. Domain logic stays framework-independent (D-002).
- **Alternatives considered:** Django (heavyweight admin/ORM coupling), Flask (validation and async not built in), Litestar (smaller ecosystem).
- **Consequences:** Handlers remain thin; use cases live in the application layer behind ports.

## D-012 — Data access: SQLAlchemy 2.x + Alembic
- **Status:** Accepted
- **Decision:** Use SQLAlchemy 2.x (Core-style typed ORM) with Alembic versioned migrations, explicit transaction boundaries, and psycopg (v3) driver.
- **Reason:** Version-controlled migrations are a fixed constraint; SQLAlchemy keeps persistence details in adapters while the domain stays persistence-ignorant.
- **Alternatives considered:** Django ORM (couples to a web framework), raw psycopg (reinvents mapping and migrations), SQLModel (younger, thinner than needed).
- **Consequences:** Integration tests run against real PostgreSQL via Docker Compose; SQLite is never the verification target.

## D-013 — Frontend: React + Vite + TypeScript + Tailwind CSS
- **Status:** Accepted
- **Decision:** Use React with Vite, TypeScript, and Tailwind CSS as the base required by shadcn/ui (D-003). State updates come from server-confirmed responses (D-006).
- **Reason:** shadcn/ui's canonical, best-supported stack; Vite gives fast builds and a simple dev server inside Docker.
- **Alternatives considered:** Next.js (server rendering not required; adds framework weight), Svelte (shadcn/ui support is secondary), plain React CRA (deprecated).
- **Consequences:** The Principles Workspace renders canonical files via the API; no separate visual source of truth (D-009).

## D-014 — Package managers: pnpm (frontend), uv (Python)
- **Status:** Accepted
- **Decision:** Use pnpm for the frontend workspace (strict, reproducible lockfile) and uv for Python dependency and environment management.
- **Reason:** Both are fast, reproducible, and widely maintained; uv has become the de facto modern Python toolchain.
- **Alternatives considered:** npm/yarn (weaker strictness story), pip+venv (slower, no lockfile-first workflow), Poetry (heavier, slower resolver).
- **Consequences:** Lockfiles are committed; Docker builds install from lockfiles only.

## D-015 — Background jobs: PostgreSQL-persisted in-process task runner (initial)
- **Status:** Accepted
- **Decision:** Implement the task-runner as an in-process asyncio worker with state durably persisted in PostgreSQL (state machine, bounded concurrency, graceful shutdown). No message broker in the initial slice. Revisit a broker (e.g. Redis-based) only when measured load requires it.
- **Reason:** Satisfies the durable-task requirements and the persistence release gate with the fewest moving parts; consistent with "avoid unnecessary dependencies" and "no speculative abstractions".
- **Alternatives considered:** Celery+Redis (extra service to operate before it is needed), RQ (Redis dependency), arq (plausible later migration path if a broker is adopted).
- **Consequences:** Long Git/model operations run as durable background tasks; the event-stream (D-009, SSE) is progress-only and never authoritative.

## D-016 — First vertical slice scope
- **Status:** Accepted
- **Decision:** Slice 1 implements: Docker Compose (app + PostgreSQL with health checks, volume, non-root), Alembic initial migration, Projects CRUD (create/read/update/delete) through FastAPI → application use case → SQLAlchemy adapter, PostgreSQL-backed integration tests, truthful health/readiness endpoints, and a minimal shadcn/ui screen that lists and creates projects with server-confirmed updates and no manual refresh.
- **Reason:** Directly targets release gates `project_crud_and_durable_persistence`, `persistence_after_restart`, and `PostgreSQL_integration_tests`, plus the UI refresh gate — in that order, per the delivery rule.
- **Consequences:** Credential lifecycle, repository sync, and model adapters remain unbuilt until Slice 1 gates are verified; no merge or push without authorization.

## D-017 — Single administrator authentication
- **Status:** Accepted
- **Decision:** Caliper starts with one local administrator. Bootstrap and password rotation happen through an interactive server-side CLI prompt; only an Argon2id password hash is stored. Sessions use random opaque tokens whose SHA-256 hashes are persisted in PostgreSQL and can be revoked. Browser cookies are HttpOnly, Secure, SameSite=Strict, and scoped to `/`. LAN browser access terminates TLS at Caddy using its internal CA; clients must explicitly trust the exported root certificate.
- **Reason:** The owner selected one administrator account. The app handles repository credentials and operational controls, so project APIs require authentication and browser credentials must not traverse the LAN in plaintext.
- **Alternatives considered:** Multiple user accounts (deferred); storing passwords or bearer tokens in environment variables or operational tables (rejected).
- **Consequences:** Initial setup requires `docker compose exec api python -m caliper.cli admin init`, and each client device must trust the local Caddy root certificate. Resetting the administrator password revokes all existing sessions.

## D-018 — Initial encrypted secret store
- **Status:** Accepted
- **Decision:** Store secret payloads as individual Fernet-encrypted files in a dedicated persistent Docker volume. Store the Fernet keyring in a separate persistent Docker volume, initialize it only when no encrypted records exist, and fail closed if it is missing after secrets have been written. PostgreSQL holds only credential references and non-secret lifecycle metadata. Rotate by persisting a new-plus-old keyring before rewriting ciphertext, then retire old keys only after all records are re-encrypted.
- **Reason:** Implements the accepted secret-store boundary without placing plaintext credentials in PostgreSQL or source control, and supports recoverable rotation with authenticated Fernet encryption.
- **Alternatives considered:** Plaintext environment/database storage (rejected); external cloud KMS (deferred because the current target is a self-hosted LAN server).
- **Consequences:** The encrypted data volume and keyring volume must both be backed up and restored. Store backups separately with the keyring protected more strictly. Losing the keyring makes ciphertext unrecoverable. A key rotation interrupted mid-run leaves both keys available and can be retried.
