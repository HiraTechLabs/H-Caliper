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

## Not verified here

The workstation has no Docker Linux engine and no GnuPG installation, so no archive or restore was executed. The restore is intentionally destructive after explicit confirmation; it has not been applied to any user database or volume. Cross-store restore is not atomic. If interrupted, keep the API stopped and repeat the restore from the same complete bundle before allowing writes. The initial-acceptance backup/restore gate remains open until a Linux Docker restore drill validates the actual volumes and fresh application reads.
