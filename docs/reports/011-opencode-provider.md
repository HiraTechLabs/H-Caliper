# OpenCode provider authentication and model selection

**Status:** Implemented and verified in an isolated Docker/PostgreSQL runtime. OAuth completion with a real provider account remains dependent on the administrator's provider account and consent.

## Delivered

- Pinned OpenCode CLI `1.19.4` in a dedicated Docker build stage and run its server on the API container's loopback interface.
- Added administrator-protected discovery, status, API-key, OAuth, disconnect, and model-selection endpoints.
- Added the **AI providers** workspace screen. It renders only sanitized provider/model metadata and supported OpenCode authentication prompts; key and authorization-code inputs are password fields and are cleared after use.
- Encrypt the complete CLI auth profile through the existing Fernet Secret Store. PostgreSQL stores only the secret reference, selected model, and status. The working `auth.json` is held under the API's memory-backed `/run/caliper-opencode` directory and restored from the encrypted secret at startup.
- OAuth auto callbacks are captured on the explicit validation action so credentials survive restart. Code-based OAuth callbacks are stored after OpenCode confirms completion.
- Added PostgreSQL migration `0007_opencode_provider` and an accepted architecture decision (D-020).

## Verification

- Docker PostgreSQL integration profile: **47 passed**, including API-key save, fresh model-selection read, disconnect, persisted settings reference, and a check that the test key does not occur in the encrypted secret payload.
- Frontend component suite: **13 passed**; production TypeScript/Vite build passed.
- Backend Ruff check and format check passed; Compose configuration passed validation.
- Built API and web Docker images. Started an isolated Compose project: database, API, web, and HTTPS proxy reported healthy; API liveness/readiness and OpenCode `/global/health` returned success; the HTTPS web root returned HTTP 200.
- Removed the isolated acceptance and PostgreSQL-test containers/networks and the acceptance-only volumes after verification. No production database, provider credential, or real OAuth account was used.

## Boundaries

- These checks validate provider authentication storage and model configuration; Caliper does not issue model inference requests in this slice.
- A real provider login cannot be completed without the administrator selecting a provider and consenting through that provider. The OAuth initiation/callback interfaces use OpenCode's supported methods, but no external provider account was used in acceptance.
- Critical browser-driven end-to-end acceptance and the remaining repository/knowledge acceptance items are tracked separately in `docs/INITIAL_ACCEPTANCE_CRITERIA.md`; this report does not mark them passed.
