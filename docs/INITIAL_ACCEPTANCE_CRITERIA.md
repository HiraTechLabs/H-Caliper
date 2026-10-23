# Caliper v2 — Initial Acceptance Criteria

Do not expand into broad autonomous execution until these gates pass.

## Runtime and persistence
- [ ] Clean checkout builds reproducibly.
- [ ] Application and PostgreSQL start using documented container configuration.
- [ ] Health checks distinguish liveness from readiness.
- [ ] Data survives app-container recreation/restart.
- [ ] Backup and restore are documented and tested.

## Projects and credentials
- [ ] Project create/read/update/delete behavior is tested and documented.
- [ ] Mutations are immediately visible after server-confirmed success.
- [ ] Fresh reads return the same state.
- [ ] Credential add/validate/replace/disable/delete semantics are explicit and tested.
- [ ] Secrets never appear in UI, API responses, logs, or reports.
- [ ] Repository status distinguishes configuration from verified remote access.

## Knowledge sync and workspace
- [ ] Sync a controlled local Git repository and record repository, branch, revision, timestamp, and outcome.
- [ ] Change a source document, sync again, and see new content without manual refresh.
- [ ] Failed sync is visible and does not claim fresh content.
- [ ] Principles, Manifest, Decisions, and Graph are visually navigable.
- [ ] Graph comes from graph.yaml and invalid references are reported.

## Model providers
- [ ] Provider login has a documented supported flow and honest unsupported-provider behavior.
- [ ] Ollama endpoint validation and model discovery work where supported.
- [ ] OpenCode CLI/auth/model configuration is validated.
- [ ] Each adapter has independent tests and actionable errors.

## Quality gates
- [ ] PostgreSQL-backed integration tests pass.
- [ ] Critical UI end-to-end tests pass.
- [ ] Lint/type/build checks pass.
- [ ] Docker build/startup checks pass.
- [ ] Graph consistency checks pass.
- [ ] Report distinguishes verified behavior from blocked/manual checks.
