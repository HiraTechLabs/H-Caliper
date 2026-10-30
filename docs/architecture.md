# Architecture and security boundaries

H-Caliper separates REST/API concerns, domain services, persistence, provider adapters, workspace/Git management, and pipeline workers. API request authentication and project authorization are enforced server-side. Pipeline progression is stored in PostgreSQL rather than process memory.

## Runtime topology

```text
Browser ──HTTPS/reverse proxy── nginx/UI ──/api── FastAPI
                                            │
                                      PostgreSQL 16
                                            │
                     persistent worker ─────┘
                         │          │
                     providers   Git/workspaces
```

Compose separates DB, API, worker, and frontend. DB/workspace use named volumes. API and worker share workspace storage. Workers claim tasks with row locks; multiple workers need unique IDs and shared storage.

## Workflow and persistence

Task creation persists project, request, selected agent roles/models, retries, and validation requirements. A worker records context collection, plan, execution, validation, review, documentation, and approval transitions. Each attempt has a task-specific branch/worktree. Changes remain separate until an authorized merge approval. Plans, reports, quality results, artifacts, events, and audit records are persistent.

SQLAlchemy/Alembic models cover users/memberships, projects/repositories/workspaces, providers/models, environments, CALIPER documents/versions/proposals, task executions/stages/plans/reviews/gates/artifacts/documentation, approvals/deployments, audit, and notifications. PostgreSQL is production storage; SQLite is test-only.

Provider and repository credentials are Fernet-encrypted. Other environment JSON is metadata and must not contain raw production credentials.

## Trust boundaries

- Browser input is untrusted. Pydantic validates request schemas; authorization is checked server-side.
- Cookie-authenticated mutations use double-submit CSRF. Session cookies are HttpOnly/SameSite=Lax; production requires Secure.
- Non-admin users need project membership. Global roles do not grant arbitrary project access.
- Provider responses and AI-generated code are untrusted. Structured parsing, safe file writes, argument-vector commands, allowlists, deterministic gates, and review are defense-in-depth.
- Git clone/pull and provider URLs are network egress. Restrict destinations/routes at network/firewall level.
- Agent and validation commands run in the worker process context. This is not a hardened kernel sandbox; isolate untrusted repositories on dedicated workers.
- Production deployment is a separate service, disabled by default. A model-generated command is not production authorization.

## Observability and constraints

Liveness/readiness endpoints are `/api/v1/health` and `/api/v1/health/ready`. Task events, stages, executions, gates, approvals, and audit actions are database-backed. Configure log shipping/alerts externally. The DB polling queue is suitable for modest scale; workspaces are shared local volume, not object storage. See [limitations](known-limitations.md).
