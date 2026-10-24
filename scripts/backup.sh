#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 1 ]]; then
  echo "Usage: scripts/backup.sh BACKUP_DIRECTORY" >&2
  exit 2
fi
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
command -v gpg >/dev/null || { echo "gpg is required (install gnupg)" >&2; exit 1; }
docker compose ps --status running --services | grep -qx db || {
  echo "The Compose database service must be running." >&2
  exit 1
}
if docker compose ps --status running --services | grep -qx api; then
  echo "Stop API writes before backing up so PostgreSQL and secret volumes align." >&2
  exit 1
fi

backup_dir=$(mkdir -p -- "$1" && cd -- "$1" && pwd)
chmod 700 "$backup_dir"
temp_dir=$(mktemp -d)
trap 'rm -rf -- "$temp_dir"' EXIT

db_user=${POSTGRES_USER:-caliper}
db_name=${POSTGRES_DB:-caliper}
docker compose exec -T db pg_dump -U "$db_user" -Fc "$db_name" >"$temp_dir/database.dump"

docker compose run --rm --no-deps -T --entrypoint sh volume-archive \
  -c 'tar -C /source/secret-data -czf - .' >"$temp_dir/secret-data.tar.gz"
docker compose run --rm --no-deps -T --entrypoint sh volume-archive \
  -c 'tar -C /source/keyring -czf - .' >"$temp_dir/keyring.tar.gz"

gpg --no-symkey-cache --batch --yes --symmetric --cipher-algo AES256 \
  --output "$backup_dir/database.dump.gpg" "$temp_dir/database.dump"
gpg --no-symkey-cache --batch --yes --symmetric --cipher-algo AES256 \
  --output "$backup_dir/secret-data.tar.gz.gpg" "$temp_dir/secret-data.tar.gz"
gpg --no-symkey-cache --batch --yes --symmetric --cipher-algo AES256 \
  --output "$backup_dir/keyring.tar.gz.gpg" "$temp_dir/keyring.tar.gz"
chmod 600 "$backup_dir"/*.gpg

cat >"$backup_dir/README.txt" <<'EOF'
Caliper backup bundle
Contains PostgreSQL custom dump, encrypted secret payloads, and encrypted keyring.
Each .gpg file is encrypted separately with GnuPG AES-256 and prompts separately.
Use different passphrases for the keyring and other files. Protect the keyring
backup and its passphrase more strictly than the other files. Store this bundle
off-host. Keep the project .env and trusted Caddy CA data backed up separately.
Restore with scripts/restore.sh after reviewing README.md.
EOF
chmod 600 "$backup_dir/README.txt"
echo "Encrypted Caliper backup created in: $backup_dir"
