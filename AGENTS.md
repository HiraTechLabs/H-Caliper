# AGENTS.md — Instructions for AI Coding Agents

Canonical entry point required by `docs/IMPLEMENTATION_RULES_FOR_AI.md` rule 1.

## Mandatory reading order (before any code change)
1. `.caliper/manifest.yaml` — project identity, fixed constraints, release gates.
2. `.caliper/DECISIONS.md` — architectural decisions and their status (Proposed ≠ Approved).
3. `.caliper/GRAPH.md` + `.caliper/graph.yaml` — architecture graph (nodes stay `planned` until verified).
4. `.caliper/principles/*.md` — engineering, security, performance, testing, business, architecture, and UI principles.
5. `docs/IMPLEMENTATION_RULES_FOR_AI.md` — binding work rules.
6. `docs/INITIAL_ACCEPTANCE_CRITERIA.md` — release gates; do not expand before they pass.

## Non-negotiable rules (summary — the docs above are authoritative)
- Never treat Proposed decisions as approved. Ask before resolving open architectural choices.
- Never commit, log, or display secret values. Secrets live only behind the secret-store interface.
- Never disable SSH host verification, authentication, or authorization to make anything pass.
- Never merge, push, or deploy without explicit authorization.
- A mutation reports success only after required durable work succeeds (PostgreSQL-confirmed).
- One complete vertical slice at a time; prefer it over broad scaffolding.
- Verify mutations with: durable state + fresh read + UI update without manual refresh.
- Use real PostgreSQL integration tests for persistence behavior; SQLite is not a substitute.
- Update `docs/WORK_LOG.md` and decisions/graph when architecture or responsibilities change.

## Branch conventions
- `feature/<name>` — new work
- `FIX/<name>` — bug fixes
- `REFACTOR/<name>` — structural changes without behavior change

## Git discipline for every step
1. Work on a branch; keep `main` stable.
2. Commit in small, complete, logically-scoped units with clear messages.
3. Never commit secrets, `.env`, volumes, or generated build output (see `.gitignore`).
4. Report exact commands, results, and skipped checks in `docs/WORK_LOG.md`.
