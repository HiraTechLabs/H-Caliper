# Per-project AI model selection

**Status:** Implemented in the source branch; frontend behavior and production build verified. PostgreSQL-backed persistence and migration application are pending a Linux Docker host run.

## Delivered

- Added a project-owned model assignment row with a cascading project foreign key and constrained provider type.
- Added administrator-protected project model endpoints. The catalog contains only models from connected OpenCode providers and the latest successful Ollama discovery. Writes reject stale or invented catalog entries, commit to PostgreSQL, then return a fresh read.
- Added **Choose AI model** to project details. The administrator can assign or clear a project model and refresh available catalogs without leaving the project.
- Added decision D-021, graph responsibility, migration `0008_project_model`, README guidance, and an unchecked acceptance gate until PostgreSQL verification passes.

## Verification

- Frontend tests: **14 passed** across 6 suites, including save and server-confirmed UI update for project model selection.
- TypeScript and Vite production build passed.
- Ruff check and formatting passed.
- Offline Alembic SQL generation passed through `0008_project_model`; no database was contacted.
- `git diff --check` → passed.

## Boundaries and remaining checks

- This feature stores configuration and does not invoke model inference.
- Real PostgreSQL integration for project-scoped isolation, persisted fresh reads, catalog rejection, clear behavior, and the applied migration must run on the Linux host.
- OpenCode provider authentication still requires an administrator's provider account and consent; Ollama options require a successful model discovery.
