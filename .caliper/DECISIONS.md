# Caliper Architecture Decisions

Statuses: **Proposed** (not yet approved), **Accepted**, **Superseded**, **Rejected**. All decisions in this initial file are Proposed. The implementation agent must not silently treat them as approved.

## D-001 — PostgreSQL for operational data
- **Status:** Proposed
- **Decision:** PostgreSQL is the primary operational store. Use versioned migrations, explicit transaction boundaries, constraints, indexes, backup/restore procedures, and PostgreSQL-backed integration tests.
- **Reason:** Reliable relationships and durable state for projects, tasks, approvals, model configuration, and execution history.
- **Consequences:** PostgreSQL is required in development and deployment. SQLite is not the production operational database.

## D-002 — Python backend
- **Status:** Proposed
- **Decision:** Use Python. Select the web framework, ORM/data-access approach, migration tool, and job system explicitly before implementation; do not infer these from the language choice.
- **Consequences:** Domain logic must remain independent of the web framework and persistence implementation.

## D-003 — shadcn/ui
- **Status:** Proposed
- **Decision:** Use shadcn/ui as the UI component system. Explicitly choose and document the frontend framework, build tool, package manager, and styling conventions.
- **Consequences:** Components must be accessible, consistent, maintainable, and testable.

## D-004 — Dockerized services
- **Status:** Proposed
- **Decision:** Containerize the application and required services, including PostgreSQL. Use documented Docker Compose workflows unless a later decision chooses another orchestrator.
- **Consequences:** Define health checks, persistent volumes, non-root runtime, configuration, secret injection, backup, restore, and upgrade processes.

## D-005 — Canonical project knowledge
- **Status:** Proposed
- **Decision:** Principles, decisions, manifest, and graph remain version-controlled project files. PostgreSQL may store sync metadata and derived indexes, but does not silently replace the files as source of truth.
- **Consequences:** Display repository, branch, revision, last successful sync, and current sync status.

## D-006 — Server-confirmed UI state
- **Status:** Proposed
- **Decision:** Mutations must return a truthful outcome and resulting state/version where appropriate. The UI updates after confirmed success without requiring manual page refresh. Optimistic updates require tested rollback behavior.
- **Consequences:** Test mutation, fresh read, UI state, and persistence separately.

## D-007 — Secret-store boundary
- **Status:** Proposed
- **Decision:** Store secret values behind a dedicated interface. PostgreSQL stores references and non-sensitive metadata. The initial implementation may use an encrypted persistent store if key management, permissions, backup, recovery, rotation, and deletion semantics are documented.
- **Consequences:** Reference deletion, disabling a credential, and destroying a secret are distinct operations.

## D-008 — Separate model adapters
- **Status:** Proposed
- **Decision:** Provider login, Ollama, and OpenCode use separate adapters behind a common internal capability contract. Unsupported capabilities must be explicit.
- **Consequences:** Each adapter has independent setup validation, status checks, error mapping, and tests.

## D-009 — Visual Principles Workspace
- **Status:** Proposed
- **Decision:** Render principles, manifest, decisions, and graph as a visual workspace sourced from canonical files.
- **Consequences:** Safe Markdown, search, cross-links, accessible graph navigation, revision display, and truthful sync status are acceptance criteria.

## D-010 — Truthful status semantics
- **Status:** Proposed
- **Decision:** Distinguish configured, validated, reachable, authenticated, synchronized, stale, succeeded, and failed. Every status must define what was checked and when.
- **Consequences:** Credential existence alone must not mean repository access is Ready. HTTP 200 alone must not mean a business operation succeeded.
