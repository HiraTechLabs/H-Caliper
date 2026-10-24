# Encrypted backup and guarded restore

**Date:** 2026-10-24
**Branch:** `feature/backup-restore`
**Base:** `feature/ollama-provider` at `19ef70f`

## Delivered

- `scripts/backup.sh` produces a PostgreSQL custom dump and independent archives for encrypted secret payloads and the keyring. Each output is encrypted with GnuPG AES-256. Backup is blocked while the API can write, and output permissions are restricted.
- `scripts/restore.sh` checks the Compose project identity and service state, decrypts all three artifacts before mutation, requires a project-specific typed confirmation, restores PostgreSQL, then replaces both secret volumes.
- A Compose maintenance-profile helper mounts only the two secret volumes for archive operations. README documents installation, operation, passphrase separation, excluded server configuration, and verification.

The keyring archive must use a separate, stronger passphrase and be stored with tighter access control. The `.env` file and Caddy data/config are excluded and need separate protection.

## Verification

- Bash syntax check: **passed**.
- Compose configuration validation: **passed**.
- `git diff --check`: **passed**.

## Runtime verification update — 2026-10-24

The earlier workstation limitation was resolved. With Docker Engine 29.7.2 and Gpg4win available, the backup and restore scripts were run against the isolated Compose project `caliper-acceptance` only. The database, secret-data volume, and keyring volume were archived and encrypted with distinct test passphrases. The test project record was deleted, the bundle was restored, and the API was restarted; administrator login succeeded and a fresh API read returned the restored project with its updated values. No user database or user volume was used. The encrypted test bundle and temporary passphrase files were removed afterward; the named acceptance-test volumes were preserved.

Cross-store restore is still not atomic. If a restore is interrupted, keep the API stopped and repeat the same complete bundle before allowing writes. Production recovery should use operator-managed passphrases and protected off-host storage.
