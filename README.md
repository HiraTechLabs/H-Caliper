# Caliper

Caliper is a self-hosted software factory for project context, AI-assisted engineering workflows, verification, and controlled delivery. This repository contains the first working vertical slice: durable project management backed by PostgreSQL, a typed HTTP API, and a browser UI.

## Run locally with Docker Compose

Prerequisites: Docker Engine and Docker Compose v2. Caliper uses a single local administrator and HTTPS. By default, the HTTPS gateway binds to localhost on port `8443`.

1. Set a local database password in your shell. Do not commit it or put it in source control.

   ```powershell
   $env:POSTGRES_PASSWORD = Read-Host "Local PostgreSQL password"
   ```

2. Start the application:

   ```powershell
   docker compose up --build -d
   ```

   For LAN access, set the server's LAN IPv4 address as the bind address and certificate name. Restrict the host firewall to the authorized client device. For example, replace the sample addresses:

   ```bash
   export CALIPER_WEB_BIND=192.168.1.20
   export CALIPER_WEB_PORT=8443
   export CALIPER_SERVER_NAME=192.168.1.104
   docker compose up --build -d
   ```

   Keep the same environment values when recreating the Compose services. The app UI container is private to the Compose network; Caddy provides HTTPS and stores its local CA in persistent Docker volumes.

3. Initialize the administrator once. The password is entered interactively and only its Argon2id hash is stored:

   ```bash
   docker compose exec api python -m caliper.cli admin init
   ```

   To rotate the password later, use `docker compose exec api python -m caliper.cli admin reset-password`; this revokes all active browser sessions.

   The `secret-init` service creates the encryption keyring automatically on first start only while the encrypted secret volume is empty. A missing keyring after secrets exist stops API startup rather than generating a replacement key. Rotate keys with `docker compose exec api python -m caliper.cli secrets rotate-key`; this rewrites stored ciphertext before retiring the old key.

4. Export Caddy's local root certificate on the server, then transfer it to the client through a trusted channel:

   ```bash
   docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt ./caliper-root.crt
   ```

   On a Windows client, open PowerShell in the certificate folder and trust it for the current user:

   ```powershell
   Import-Certificate -FilePath .\caliper-root.crt -CertStoreLocation Cert:\CurrentUser\Root
   ```

   Open `https://<server-LAN-IPv4>:8443` on the client (or `https://localhost:8443` on the server). The API is available through the HTTPS gateway at `/api`; OpenAPI docs are at `/api/docs`. A private CA certificate must be trusted on each client device before the browser accepts the connection.

The PostgreSQL data volume is named `postgres-data` and survives container recreation. Do not remove it to troubleshoot the application. Liveness (`/health/live`) reports whether the API process is running; readiness (`/health/ready`) checks PostgreSQL.

Project details include credential management for HTTPS Git access tokens. The API returns only the credential name, username, and lifecycle metadata; saved token values cannot be viewed again. `Configured` means a token was safely stored, not that it works with the remote. `Reachable` means Git successfully queried the remote while sending the configured authorization header; a public remote may allow anonymous reads, so this does not always confirm the token's identity. Disable retains the encrypted secret for later re-enabling; replace saves the new token and clears its old encrypted value; delete destroys the secret. Remove credentials before deleting their project. SSH private-key credentials are not supported in this first implementation because trusted SSH host keys have not been provisioned.

Encrypted secret payloads and their keyring use separate `caliper-secret-data` and `caliper-keyring` volumes. Back up both before upgrades and store the keyring backup in a separately access-controlled, encrypted location. A database backup alone cannot recover credentials; losing the keyring makes the encrypted payloads unrecoverable. Do not commit either backup or remove either volume as troubleshooting.

## Verify PostgreSQL persistence

The integration profile creates a separate ephemeral PostgreSQL database whose name is `caliper_test`. It never targets the application database.

```powershell
docker compose --profile test run --build --rm integration-tests
```

Run the browser-state component checks and production build from `web/` with `pnpm test` and `pnpm build`.

For local backend development, install the locked dependencies with `uv sync`, set `CALIPER_DATABASE_URL` to a disposable PostgreSQL database, then run migrations using `uv run alembic upgrade head` and tests using `uv run pytest` from `backend/`.

## Back up and restore

From a Bash-compatible shell, back up the operational database with `docker compose exec -T db pg_dump -U caliper -Fc caliper > caliper.dump`. Restore into a separately created database after stopping API writes with `docker compose exec -T db pg_restore -U caliper -d caliper --clean --if-exists < caliper.dump`. Keep backups encrypted and access-controlled. A restore has not yet been exercised as part of this initial slice.

## Current scope

The single administrator can sign in through an HttpOnly, Secure, SameSite=Strict session cookie. Password hashes and hashed, revocable session tokens are stored in PostgreSQL; project and credential endpoints require an active session. Project and credential metadata commit to PostgreSQL before the API reports success; credential payloads are stored only in the encrypted secret store. The credential UI supports add, check access, replace, disable, and delete. Repository knowledge synchronization, model adapters, durable background tasks, and the visual Principles Workspace remain later vertical slices.
