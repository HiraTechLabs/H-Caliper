# Ollama provider configuration and discovery

**Date:** 2026-10-24  
**Branch:** `feature/ollama-provider`  
**Base:** `feature/principles-workspace` at `f4d228c`

## Delivered

- Administrator-only API to save and read an Ollama endpoint, check reachability, and select a discovered model.
- Bounded `GET /api/tags` discovery: four-second timeout, no redirects or environment proxy use, response-size and catalog limits, and safe error codes.
- PostgreSQL migration `0006_ollama_provider` and repository behavior that persists discovery state, returns fresh reads, and invalidates model selection when the endpoint changes.
- UI for endpoint configuration, validation, discovered models, and selection. Only model IDs from the persisted catalog can be selected.
- README and architecture graph description updates. Graph status remains `planned` pending release-gate verification.

This slice configures an Ollama service only. It does not implement account login, OpenCode integration, or inference.

## Verification

- Focused backend unit tests: **10 passed**.
- Backend Ruff check and format check: **passed** (57 files formatted).
- Frontend tests: **11 passed**.
- Frontend TypeScript and production build: **passed**.
- PostgreSQL DDL generation: **passed through migration 0006**; generated offline and not applied.
- FastAPI OpenAPI inspection: all three Ollama endpoints registered.
- Docker Compose configuration validation: **passed**.
- `git diff --check`: **passed before final commit review**.

## Not verified here

The local Docker Linux engine is unavailable. Therefore PostgreSQL integration persistence, applying migration 0006, container startup, live Ollama discovery, and browser-to-backend flow need verification on the Linux host. No database was mutated and no deployment or push was performed.
