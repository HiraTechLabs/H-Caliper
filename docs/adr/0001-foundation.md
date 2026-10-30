# ADR 0001: Backend, persistence, and worker foundation

**Status:** Accepted

## Decision

Use FastAPI + async SQLAlchemy 2 + PostgreSQL 16 + Alembic, a React/Vite TypeScript frontend, and a database-polled persistent worker rather than introducing Redis/Celery for the initial deployment.

## Rationale

The application is API and workflow heavy, PostgreSQL provides durable task state and row-lock claiming, and modest initial operations benefit from fewer services. React/Vite enables a separately buildable UI. Git worktrees isolate task modifications.

## Consequences

Migrations and workflow recovery are database-backed. Queue throughput is bounded by polling/DB capacity; add a broker only when measured requirements justify it. Task execution still needs a hardened sandbox for hostile repositories.
