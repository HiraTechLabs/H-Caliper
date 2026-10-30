# Deployment operations

Compose services are PostgreSQL 16 (`db`), FastAPI (`backend`), persistent pipeline worker (`worker`), and nginx static UI/API proxy (`frontend`). DB and workspace data use named volumes. API entrypoint applies Alembic migrations before serving.

## Ports and public deployment

Defaults: UI `8080`, API `8001`, PostgreSQL `5433`. Local convenience mappings are not a public-production firewall. Remove DB host port and bind API/UI to loopback behind a hardened TLS reverse proxy, or firewall them:

```yaml
services:
  db:
    ports: []
  backend:
    ports:
      - "127.0.0.1:8001:8000"
  frontend:
    ports:
      - "127.0.0.1:8080:80"
```

Set `TRUSTED_PROXY_COUNT` to the real trusted chain. The included nginx server is plain HTTP; terminate TLS at trusted ingress. Keep `COOKIE_SECURE=true` externally.

## Start and verify

Follow README quick start; then:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 backend worker frontend
curl -fsS http://127.0.0.1:8080/health
```

Back up DB and workspace before updates. Review migrations and test a task before accepting a release. `docker compose down` preserves volumes. **Do not use `docker compose down -v`** unless intentionally destroying all persisted H-Caliper data.

## Worker integrations

Default container does not install/authenticate OpenCode, Codex, Antigravity, or Docker CLI binaries. A reviewed custom worker image and least-privileged noninteractive auth are required. Docker-backed health checks additionally require explicit Docker socket access; this is effectively host-level control. Do not mount a developer home/token directory wholesale.

Monitor DB/storage readiness, worker logs, free disk, failed tasks, provider status, and backup success. The minimum practical deployment is 2 vCPU and 4 GB RAM; build tool memory and repository size vary.
