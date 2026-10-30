# Verification status

Do not assume checks on a development machine prove another provider, repository, or deployment is operational.

## Automated checks

- Backend command `../.venv/bin/python -m pytest -q`: **18 passed in 285.38s** (2026-10-30). Uses isolated SQLite and temporary Git repositories; PostgreSQL-specific integration remains necessary.
- Backend `../.venv/bin/ruff check app tests --select F --output-format concise`: passed (2026-10-30).
- Backend `../.venv/bin/python -m compileall -q app alembic tests`: passed (2026-10-30).
- Frontend `npm run build` (includes `tsc -b`): passed (2026-10-30). Manual chunks emitted; no bundle-size warning in the recorded run.
- `docker compose --env-file /tmp/hcaliper-compose-check.env config --quiet`: passed (2026-10-30).
- A prior end-to-end development run used MockProvider for plan → execute → gates → review → documentation → human-approved merge. This is test-provider evidence only, not real provider connectivity evidence.

## Not verified externally

- FreeLLMAPI and LM Studio endpoints/credentials unavailable here.
- OpenCode/Codex/Antigravity CLI installation/auth are host-specific; CLIs are not included in default container.
- Live GitHub clone/push/PR requires configured real credentials and a remote acceptance run.
- Production deployment was not enabled/tested against a live environment.
- Docker Compose image builds passed for backend, worker, and frontend on 2026-10-30. Backend/worker were rebuilt after removing the unnecessary `docker.io` package. No containers were started by this work. PostgreSQL migration/runtime smoke testing remains unverified.

Docker/Compose backend images no longer install the Docker Engine package by default, reducing the image footprint. Docker-backed environment checks require a deliberately customized image and explicit Docker socket access; socket access is effectively host-level control. Do not enable it without isolated-host review.

Change “not verified” only with recorded evidence from the target deployment.
