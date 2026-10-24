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

## Synchronize repository knowledge

Open a project and choose **Repository knowledge**. Synchronization checks out the configured branch in a short-lived temporary directory, reads Markdown, MDX, YAML, TOML, and JSON files from `.caliper/`, `docs/`, `README.md`, and `AGENTS.md`, removes configured credential values and common token/private-key patterns, then stores the derived snapshot and revision in PostgreSQL. The temporary clone is deleted after each operation. Repository content is untrusted and is displayed as escaped plain text, never as executable HTML. Files larger than 1 MiB, snapshots larger than 10 MiB, trees larger than 64 MiB, and trees with more than 20,000 entries are rejected.

For a controlled local Git repository, place a **bare** repository under `local-repositories/` and opt in explicitly before starting Compose:

```bash
export CALIPER_ALLOW_LOCAL_REPOSITORIES=true
```

Use its `file://` URL in the project settings. The API mounts this directory read-only and rejects local paths outside it. Local repository access is disabled by default. For SSH read access, place administrator-verified host keys in `config/ssh/known_hosts`; strict host-key checking stays enabled. HTTPS credentials are selected per synchronization and are never returned by the API.

The project panel shows `configured`, `queued`, `running`, `synchronized`, `stale`, or `failed`, along with branch, revision, last successful timestamp, and the current document snapshot. A failed refresh retains the last successful snapshot and reports it as stale; a first failed attempt is marked failed. Only one synchronization can be queued or run per project, and deleting a project is blocked while it is active. Sync requests are persisted in PostgreSQL and executed by one in-process worker; after a server restart interrupted jobs are retried up to three attempts. The queue accepts at most 1,000 waiting tasks. The authenticated API returns after the task is durably queued, while the browser follows its status. PostgreSQL is authoritative for queue state, sync status, and knowledge content.

Choose **Principles workspace** in a project's details to navigate its synchronized Principles, Manifest, Decisions, and Graph views. Markdown is rendered with HTML disabled and sanitized; internal links stay inside the saved snapshot. The Graph view parses `.caliper/graph.yaml` from the same confirmed revision, displays component status as text, and reports malformed YAML, duplicate node IDs, or edges that reference missing nodes. The view always shows repository, branch, revision, last successful sync, and whether the saved snapshot is stale. It does not substitute local UI data for repository knowledge.

Encrypted secret payloads and their keyring use separate `caliper-secret-data` and `caliper-keyring` volumes. Back up both before upgrades and store the keyring backup in a separately access-controlled, encrypted location. A database backup alone cannot recover credentials; losing the keyring makes the encrypted payloads unrecoverable. Do not commit either backup or remove either volume as troubleshooting.

## Connect Ollama

Open **Ollama** from the workspace navigation, enter the endpoint that the Caliper API container can reach, save it, then choose **Validate and discover**. For Ollama running on the Docker host, `http://host.docker.internal:11434` is a common endpoint; its availability depends on the host's Docker networking. Caliper queries only `/api/tags`, follows no redirects, applies a four-second timeout and a one-megabyte response limit, then stores the connection status and discovered model names in PostgreSQL. Selectable model IDs must come from the latest successful discovery. Changing the endpoint clears the prior catalog and selection.

The Ollama adapter does not support endpoint passwords, API keys, or inference yet. Use an endpoint reachable and trusted by the self-hosted Caliper server; HTTP sends requests without transport encryption, so use HTTPS when the endpoint is reached over an untrusted network. Model IDs and endpoint URL are configuration metadata, not credentials.

## Connect hosted model providers

Open **AI providers** in the workspace navigation. Caliper uses the pinned OpenCode CLI runtime to list supported providers, provider-specific API-key and OAuth flows, and available models. Choose a provider, complete one of its displayed sign-in methods, then choose a model from a connected provider. OAuth providers may use a browser authorization page and either return a code or complete automatically; follow the instructions shown by OpenCode. Providers requiring a flow that OpenCode does not expose are not offered as supported methods.

Caliper encrypts the complete OpenCode authentication profile with its Fernet Secret Store and stores only the encrypted profile reference and model selection in PostgreSQL. The CLI reads a temporary profile under the API container's memory-backed `/run/caliper-opencode` directory. On restart the profile is restored from encrypted storage; if decryption fails, Caliper reports the provider service as unavailable. Disconnecting a provider removes its authorization from the profile. The UI accepts secrets in password fields and does not return them from the API. The chosen model is configuration only; this slice does not yet send inference requests.

## Verify PostgreSQL persistence

The integration profile creates a separate ephemeral PostgreSQL database whose name is `caliper_test`. It never targets the application database.

```powershell
docker compose --profile test run --build --rm integration-tests
```

Run the browser-state component checks and production build from `web/` with `pnpm test` and `pnpm build`.

For local backend development, install the locked dependencies with `uv sync`, set `CALIPER_DATABASE_URL` to a disposable PostgreSQL database, then run migrations using `uv run alembic upgrade head` and tests using `uv run pytest` from `backend/`.

## Back up and restore

Run these commands on the Linux server from the project directory. Install Docker Compose and GnuPG (`gpg`). Stop API writes before the backup so the PostgreSQL dump and encrypted-secret volumes represent one consistent point in time:

```bash
docker compose stop api
bash scripts/backup.sh /path/on/encrypted/storage/caliper-backups/$(date +%Y%m%d-%H%M%S)
docker compose start api
```

The script creates separate AES-256 GnuPG-encrypted files for PostgreSQL, secret payloads, and the keyring. It prompts for each file; use one passphrase for the database and payload archive and a different, stronger passphrase for the keyring. Store the keyring backup and its passphrase separately with stricter access control. Keep the backup off-host. Also protect the project `.env` (database password) and Caddy internal-CA data/config volumes separately; these are not included. The script requires the database running and refuses to run while the API is active.

To restore, first stop API writes, then run the restore command with the Compose project name shown by `docker compose ls`:

```bash
docker compose stop api
bash scripts/restore.sh /path/to/caliper-backup PROJECT_NAME
docker compose start api
```

The script checks that the named project matches the current database container, decrypts and validates all archive files before changing state, and requires typing `RESTORE-PROJECT_NAME`. It refuses to run while `api` or `secret-init` is active. It replaces the configured database and both secret volumes; do not run it against the wrong Compose project. After restore, verify administrator login, projects, and credentials before resuming service. Keep the source backup until those checks pass. Restore execution and volume recovery still require validation on the Linux Docker host before this acceptance gate can be marked complete.

## Current scope

The single administrator can sign in through an HttpOnly, Secure, SameSite=Strict session cookie. Password hashes and hashed, revocable session tokens are stored in PostgreSQL; project, credential, and knowledge endpoints require an active session. Project, credential, task, provider settings, sync status, and knowledge metadata commit to PostgreSQL before the API reports success; credential and provider-authentication payloads are stored only in the encrypted secret store. The UI supports project and credential lifecycle, durable repository sync, safe knowledge browsing, a revisioned Principles Workspace, Ollama endpoint validation/model discovery, and OpenCode provider login and model selection. Model inference and autonomous execution remain outside this release slice.
