# Caliper v2 — Initial Acceptance Criteria

Do not expand into broad autonomous execution until these gates pass.

## Runtime and persistence
- [x] Clean checkout builds reproducibly.
- [x] Application and PostgreSQL start using documented container configuration.
- [x] Health checks distinguish liveness from readiness.
- [x] Data survives app-container recreation/restart.
- [x] Backup and restore are documented and tested.

## Projects and credentials
- [x] Project create/read/update/delete behavior is tested and documented.
- [x] Mutations are immediately visible after server-confirmed success.
- [x] Fresh reads return the same state.
- [x] Credential add/validate/replace/disable/delete semantics are explicit and tested.
- [x] Secrets never appear in UI, API responses, logs, or reports.
- [x] Repository status distinguishes configuration from verified remote access.

## Knowledge sync and workspace
- [x] Sync a controlled local Git repository and record repository, branch, revision, timestamp, and outcome.
- [x] Change a source document, sync again, and see new content without manual refresh.
- [x] Failed sync is visible and does not claim fresh content.
- [x] Principles, Manifest, Decisions, and Graph are visually navigable.
- [x] Graph comes from graph.yaml and invalid references are reported.

## Model providers
- [x] Provider login has a documented supported flow and honest unsupported-provider behavior.
- [ ] Ollama endpoint validation and model discovery work where supported.
- [x] OpenCode CLI/auth/model configuration is validated.
- [x] Each adapter has independent tests and actionable errors.

## Quality gates
- [x] PostgreSQL-backed integration tests pass.
- [ ] Critical UI end-to-end tests pass.
- [x] Lint/type/build checks pass.
- [x] Docker build/startup checks pass.
- [x] Graph consistency checks pass.
- [x] Report distinguishes verified behavior from blocked/manual checks.
