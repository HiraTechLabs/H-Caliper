# Task report 005 — Project credential lifecycle

**Date:** 2026-10-24  
**Branch:** `feature/secret-store`  
**Decision:** D-019 accepts HTTPS tokens as the initial credential type.

## Implemented

- Project-scoped HTTPS token records with unique per-project names and metadata in PostgreSQL.
- Encrypted token payloads stored only through the secret-store adapter.
- Authenticated API and UI flows for add, list, replace, disable, enable, check access, and delete.
- API responses omit the token and secret-store reference.
- Replacement cleanup is retryable; deletion first disables the row, destroys active and prior encrypted payloads, and then removes metadata. Project deletion returns a conflict while credentials remain.
- Git remote checking uses `git ls-remote` with a bounded timeout, redirects disabled, authorization in the child-process environment, and stdout/stderr discarded.
- A successful check is labeled `reachable`, not `authenticated`, because a public remote may permit anonymous access.

## Verification

- Backend: Ruff passed; 13 tests passed, including credential use-case and Git argument/redaction checks. Five PostgreSQL integration tests were skipped because there was no test database.
- Frontend: 8 behavior tests passed; TypeScript/Vite production build passed.
- Compose config validation passed.
- Alembic generated offline PostgreSQL DDL through migration `0003_project_credentials`.

## Not verified

The local Docker engine was unavailable. PostgreSQL persistence and the real HTTP API lifecycle test, applied migrations, actual token acceptance against a remote, and cleanup behavior in Docker volumes still require execution on the Linux server. SSH private keys remain unsupported; no host-key verification has been weakened.
