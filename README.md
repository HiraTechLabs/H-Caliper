# Caliper

Caliper is a self-hosted software factory for project context, AI-assisted engineering workflows, verification, and controlled delivery. This repository contains the first working vertical slice: durable project management backed by PostgreSQL, a typed HTTP API, and a browser UI.

## Run locally with Docker Compose

Prerequisites: Docker Engine and Docker Compose v2. The initial slice has no user authentication and binds to localhost by default. To access it from a private LAN, bind to the server's specific LAN IPv4 address and restrict the host firewall to the authorized client address. Do not bind to `0.0.0.0` or expose the app to an untrusted network.

1. Set a local database password in your shell. Do not commit it or put it in source control.

   ```powershell
   $env:POSTGRES_PASSWORD = Read-Host "Local PostgreSQL password"
   ```

2. Start the application:

   ```powershell
   docker compose up --build -d
   ```

   For LAN access, set `CALIPER_WEB_BIND` to the server's LAN IPv4 address and add a host firewall rule allowing the web port only from the authorized client's IPv4 address. For example, replace the sample address and port as needed:

   ```bash
   export CALIPER_WEB_BIND=192.168.1.20
   export CALIPER_WEB_PORT=8080
   docker compose up --build -d
   ```

   The firewall command depends on the host firewall in use. Do not start with the LAN binding until that source-restricted rule is in place. Keep the same environment values when recreating the Compose services.

3. Open `http://localhost:8080` on the server, or `http://<server-LAN-IPv4>:8080` from the authorized LAN client. The API is available through the UI gateway at `/api`; OpenAPI docs are at `/api/docs`.

The PostgreSQL data volume is named `postgres-data` and survives container recreation. Do not remove it to troubleshoot the application. Liveness (`/health/live`) reports whether the API process is running; readiness (`/health/ready`) checks PostgreSQL.

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

Projects support create, list, read, update, and delete. Project changes commit to PostgreSQL before the API reports success; the UI renders the response returned by the server. Credential management, repository synchronization, model adapters, durable background tasks, and the visual Principles Workspace are later vertical slices.
