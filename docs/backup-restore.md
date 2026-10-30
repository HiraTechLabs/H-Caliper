# Backup and restore

Back up PostgreSQL, workspace/repository volume, and the matching encryption/configuration keys. Use encrypted off-host storage and retention rotation. Key material must be kept separately from the data backup. Without the matching `ENCRYPTION_KEY`, credential ciphertext cannot be decrypted.

## Backup

```bash
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > "backups/hcaliper-${stamp}.dump"
docker run --rm -v h-caliper_workspace_data:/data:ro \
  -v "$PWD/backups:/backup" alpine \
  tar -czf "/backup/workspaces-${stamp}.tar.gz" -C /data .
```

For large installations, use snapshot/incremental tooling and coordinate DB/workspace consistency by pausing tasks or taking consistent snapshots.

## Restore drill

Use an isolated test host and compatible release. Restore matching protected keys, workspace volume, and DB dump. Example DB restore into a clean instance:

```bash
docker compose stop backend worker
cat backups/hcaliper-YYYYMMDDTHHMMSSZ.dump | \
  docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    --clean --if-exists --no-owner
docker compose up -d backend worker frontend
curl -fsS http://127.0.0.1:8080/health
```

Verify projects, task history, audit records, restored workspaces, and a safe provider test. Record recovery time and missing state. Never restore over production without explicit change control. Losing the encryption key means re-entering credentials after data restore.
