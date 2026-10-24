#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

if [[ $# -ne 2 ]]; then
  echo "Usage: scripts/restore.sh BACKUP_DIRECTORY COMPOSE_PROJECT_NAME" >&2
  exit 2
fi
command -v docker >/dev/null || { echo "docker is required" >&2; exit 1; }
command -v gpg >/dev/null || { echo "gpg is required (install gnupg)" >&2; exit 1; }
backup_dir=$(cd -- "$1" && pwd)
project_name=$2
[[ "$project_name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || {
  echo "Invalid Compose project name." >&2
  exit 2
}
for file in database.dump.gpg secret-data.tar.gz.gpg keyring.tar.gz.gpg; do
  [[ -s "$backup_dir/$file" ]] || { echo "Missing backup file: $file" >&2; exit 1; }
done

running_services=$(docker compose ps --status running --services)
if grep -qx api <<<"$running_services" || grep -qx secret-init <<<"$running_services"; then
  echo "Stop the API and secret-init services before restoring." >&2
  exit 1
fi
grep -qx db <<<"$running_services" || {
  echo "The Compose database service must be running." >&2
  exit 1
}
db_container=$(docker compose ps -q db)
actual_project=$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$db_container")
[[ "$actual_project" == "$project_name" ]] || {
  echo "Compose project mismatch: expected $project_name, found $actual_project." >&2
  exit 1
}

printf 'This replaces the database and both secret volumes for Compose project %s.\n' "$project_name"
read -r -p "Type RESTORE-$project_name to continue: " confirmation
[[ "$confirmation" == "RESTORE-$project_name" ]] || { echo "Restore cancelled."; exit 1; }

temp_dir=$(mktemp -d)
trap 'rm -rf -- "$temp_dir"' EXIT
gpg --no-symkey-cache --quiet --decrypt --output "$temp_dir/database.dump" "$backup_dir/database.dump.gpg"
gpg --no-symkey-cache --quiet --decrypt --output "$temp_dir/secret-data.tar.gz" "$backup_dir/secret-data.tar.gz.gpg"
gpg --no-symkey-cache --quiet --decrypt --output "$temp_dir/keyring.tar.gz" "$backup_dir/keyring.tar.gz.gpg"
validate_tar_paths() {
  local archive=$1 member
  while IFS= read -r member; do
    case "$member" in
      /*|../*|*/../*|*/..) echo "Unsafe path in backup archive." >&2; return 1 ;;
    esac
  done < <(tar -tzf "$archive")
}
validate_tar_paths "$temp_dir/secret-data.tar.gz"
validate_tar_paths "$temp_dir/keyring.tar.gz"
tar -tzf "$temp_dir/keyring.tar.gz" | grep -qx './keyring.json' || {
  echo "The keyring archive does not contain keyring.json." >&2
  exit 1
}
docker compose exec -T db pg_restore --list <"$temp_dir/database.dump" >/dev/null

db_user=${POSTGRES_USER:-caliper}
db_name=${POSTGRES_DB:-caliper}
docker compose exec -T db pg_restore --exit-on-error --clean --if-exists \
  -U "$db_user" -d "$db_name" <"$temp_dir/database.dump"

docker compose run --rm --no-deps -T --entrypoint sh volume-archive -c \
  'find /source/secret-data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -C /source/secret-data -xzf -' \
  <"$temp_dir/secret-data.tar.gz"
docker compose run --rm --no-deps -T --entrypoint sh volume-archive -c \
  'find /source/keyring -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -C /source/keyring -xzf -' \
  <"$temp_dir/keyring.tar.gz"
echo "Restore completed. Start the API and verify administrator login, projects, and credentials before resuming use."
