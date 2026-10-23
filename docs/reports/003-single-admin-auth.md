# Task report 003 — Single administrator authentication

**Date:** 2026-10-24  
**Branch:** `feature/single-admin-auth`  
**Decision:** D-017 accepted after owner selected one administrator account.

## Implemented

- Interactive server-side setup and password rotation; minimum 12 characters, maximum 1024.
- Argon2id password hashes; no plaintext password persistence or logging.
- Opaque random browser tokens; only SHA-256 token hashes are stored in PostgreSQL.
- Twelve-hour, revocable sessions. Rotating the password invalidates all sessions.
- Project routes require a valid session. The API sets HttpOnly, Secure, SameSite=Strict cookies and checks request Origin when provided.
- Sign-in and first-run setup guidance in the UI.
- Caddy TLS termination with persistent internal CA storage; UI remains private on the Compose network.
- README, architecture decision, graph, and work log updated.

## Verification

- Frontend: 6 tests passed; TypeScript and Vite production build passed.
- Backend: 6 tests passed; 4 PostgreSQL integration tests skipped because no test database is configured.
- Ruff lint and formatting passed after auto-fixing import order.
- `docker compose config --quiet` passed with a dummy validation password.
- `git diff --check` passed.

## Not verified

Docker Desktop's Linux engine was unavailable. The Alembic migration was not applied to PostgreSQL; Docker images, Caddy CA issuance, browser trust, authenticated live requests, session revocation against PostgreSQL, LAN HTTPS access, persistence/restart, and backup/restore still need verification on the Linux server. Keep architecture graph statuses planned until these checks pass.

## Server setup

Follow README's HTTPS LAN steps. Use `CALIPER_WEB_BIND` and `CALIPER_SERVER_NAME` set to the server LAN IP, expose TCP 8443 only to authorized clients, run `docker compose exec api python -m caliper.cli admin init`, export the public Caddy root certificate, and trust it in `Cert:\CurrentUser\Root` on each Windows client. Password rotation uses `docker compose exec api python -m caliper.cli admin reset-password`.
