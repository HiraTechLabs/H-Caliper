# Testing Principles

Use unit, integration, contract, end-to-end, and security tests in balance.

For each critical mutation, verify request validation, business behavior, durable state, a fresh read, UI state, restart persistence where required, failure behavior, and isolation from other projects.

- Use isolated PostgreSQL integration environments and the same migrations as the application.
- Test constraints, transactions, rollback, deletion semantics, and concurrency where relevant.
- Do not substitute SQLite or mocks for tests whose purpose is to verify PostgreSQL persistence.
- Use temporary local Git repositories for deterministic repository tests; do not claim these prove real GitHub access.
- Test credential redaction in UI, APIs, logs, and errors.
- Test UI behavior, not just button presence: visible success/failure, stale-state removal, loading completion, and no false success.
- Run focused tests, full suite, lint/type/build checks, migrations on a clean database, Docker build/startup, and graph checks as applicable.
- Record exact commands, pass/fail counts, skips, and environment limitations. Never say all tests pass if a relevant check failed or was skipped.
