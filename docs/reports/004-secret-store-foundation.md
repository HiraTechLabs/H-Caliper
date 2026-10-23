# Task report 004 — Encrypted secret-store foundation

**Date:** 2026-10-24  
**Branch:** `feature/secret-store`  
**Decision:** D-018 records the chosen self-hosted encrypted store.

## Implemented

- Application-facing `SecretStore` protocol with UUID references.
- Per-secret encrypted files using Fernet authenticated encryption.
- Separate keyring and encrypted-data directories, expected to be backed by separate Compose volumes.
- First-run key initialization only when the data store is empty; missing keys with existing records fail closed.
- Interrupted key rotation retains both keys so rotation can be retried; after all records rotate, the old key is removed.
- CLI commands for keyring initialization and rotation.
- Unit tests cover encrypted contents, restart reads, deletion, rotation, and key-loss behavior.

## Verification

- Backend lint passed.
- Backend suite: 10 passed, 4 PostgreSQL integration tests skipped because no PostgreSQL test database was available.
- Compose configuration validation passed with a dummy database password.

## Not verified

The Docker engine was unavailable locally, so named volume setup/ownership, container startup ordering, and backup/restore have not been exercised. Credential metadata, API/UI lifecycle, remote validation, and repository sync remain to be implemented. This report does not claim those acceptance criteria are complete.

## Recovery requirements

Back up encrypted secret data and the keyring separately. Protect the keyring backup more strictly than ciphertext. Restore both before starting the API. If ciphertext exists but the keyring is lost, the data cannot be recovered; the application intentionally fails closed. Key rotation may be retried while the keyring contains both old and new keys.
