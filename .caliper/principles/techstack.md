# Technology Stack Principles

## Fixed constraints
- Backend: Python.
- Operational database: PostgreSQL.
- UI component system: shadcn/ui.
- Application and required services: Dockerized.
- Model connection methods: provider login, Ollama, OpenCode.

These constraints do not by themselves select a frontend framework, API framework, ORM, migration tool, package manager, or background-job system. Compare and record those choices before implementation.

## PostgreSQL
Use version-controlled migrations, explicit transaction boundaries, constraints, deliberate deletion semantics, appropriate indexes, connection pooling, and documented backup/restore. Test persistence with real PostgreSQL integration tests; SQLite is not a substitute for PostgreSQL-specific behavior.

## Docker
Use reproducible builds, declared dependencies, non-root runtime where feasible, explicit persistent volumes, health checks, graceful shutdown, and versioned images. Never bake secrets into images. Document configuration and backup/restore. Do not delete volumes as routine troubleshooting.

## General
Pin or constrain dependencies; prefer maintained libraries; validate configuration at startup; keep development and CI reproducible; avoid unnecessary dependencies; document upgrades. Every major dependency requires a rationale and security/maintenance review.
