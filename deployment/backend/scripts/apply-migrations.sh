#!/usr/bin/env bash
set -euo pipefail

deploy_root="${1:?deploy root is required}"
release_dir="${2:?release directory is required}"
backup_reference="${3:?verified backup reference is required}"
image_ref="${4:?immutable application image is required}"
migration_env="$deploy_root/env/migration.env"
backup_marker="$deploy_root/backups/verified-$backup_reference"

[[ -f "$backup_marker" && ! -L "$backup_marker" ]] \
  || { echo "Migration refused: verified backup marker is missing." >&2; exit 1; }
[[ "$(stat -c '%U:%G %a' "$backup_marker")" == "root:root 600" ]] \
  || { echo "Migration refused: verified backup marker must be root:root mode 600." >&2; exit 1; }
[[ -f "$migration_env" && ! -L "$migration_env" ]] \
  || { echo "Migration refused: restricted migration.env is missing." >&2; exit 1; }
[[ "$(stat -c '%U:%G %a' "$migration_env")" == "root:root 600" ]] \
  || { echo "Migration refused: migration.env must be root:root mode 600." >&2; exit 1; }

load_literal_env_value() {
  local key="$1" file="$2" line value="" found="false"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" == "$key="* ]] || continue
    [[ "$found" == "false" ]] \
      || { echo "Migration refused: migration.env contains a duplicate required key." >&2; exit 1; }
    value="${line#*=}"
    found="true"
  done < "$file"
  [[ "$found" == "true" && -n "$value" ]] \
    || { echo "Migration refused: migration.env is missing a required value." >&2; exit 1; }
  printf -v "$key" '%s' "$value"
  export "$key"
}

# Parse only the two literal keys this operation owns. Never source an env file.
load_literal_env_value SUPABASE_DB_DIRECT_URL "$migration_env"
load_literal_env_value SUPABASE_PROJECT_REF "$migration_env"
command -v supabase >/dev/null 2>&1 \
  || { echo "Migration refused: the pinned Supabase CLI is not installed on Oracle." >&2; exit 1; }
expected_cli_version="$(tr -d '[:space:]' < "$release_dir/supabase-cli.version")"
[[ "$expected_cli_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] \
  || { echo "Migration refused: the release Supabase CLI pin is invalid." >&2; exit 1; }
actual_cli_version="$(supabase --version | tr -d '[:space:]')"
[[ "$actual_cli_version" == "$expected_cli_version" ]] \
  || { echo "Migration refused: the Oracle Supabase CLI version does not match the release pin." >&2; exit 1; }

docker run --rm -i \
  --env SUPABASE_DB_DIRECT_URL \
  --env SUPABASE_PROJECT_REF \
  "$image_ref" \
  python - <<'PY'
import os
import re
from urllib.parse import urlsplit

url = os.environ["SUPABASE_DB_DIRECT_URL"]
project_ref = os.environ["SUPABASE_PROJECT_REF"]
parsed = urlsplit(url)
if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
    raise SystemExit("Migration refused: direct database URL is invalid.")
if not re.fullmatch(r"[a-z0-9]{20}", project_ref):
    raise SystemExit("Migration refused: SUPABASE_PROJECT_REF is invalid.")
if parsed.hostname.casefold() != f"db.{project_ref}.supabase.co" or parsed.port not in {None, 5432}:
    raise SystemExit("Migration refused: direct database host does not match SUPABASE_PROJECT_REF.")
PY

log_dir="$deploy_root/migration-logs"
install -d -m 700 -o root -g root "$log_dir"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
dry_run_log="$log_dir/${timestamp}-${SUPABASE_PROJECT_REF}-dry-run.log"
apply_log="$log_dir/${timestamp}-${SUPABASE_PROJECT_REF}-apply.log"

print_redacted_log() {
  sed -E \
    -e 's#(postgres(ql)?://)[^[:space:]]+#\1[REDACTED]#g' \
    -e 's#(password|token|secret)([=:][^[:space:]]+)#\1=[REDACTED]#Ig' \
    "$1"
}

set +e
(
  cd "$release_dir"
  supabase db push --dry-run --db-url "$SUPABASE_DB_DIRECT_URL"
) >"$dry_run_log" 2>&1
dry_run_status=$?
set -e
chmod 600 "$dry_run_log"

# Show the migration plan while redacting any URL-like credential material.
print_redacted_log "$dry_run_log"
[[ "$dry_run_status" == "0" ]] || { echo "Migration dry run failed." >&2; exit "$dry_run_status"; }

echo "Dry run succeeded for the confirmed Supabase project; applying forward migrations."
set +e
(
  cd "$release_dir"
  supabase db push --db-url "$SUPABASE_DB_DIRECT_URL"
) >"$apply_log" 2>&1
apply_status=$?
set -e
chmod 600 "$apply_log"
[[ "$apply_status" == "0" ]] || { echo "Migration apply failed." >&2; exit "$apply_status"; }
echo "Forward migration command completed; raw output remains in the restricted Oracle migration log."

docker run --rm \
  --env SUPABASE_DB_DIRECT_URL \
  "$image_ref" \
  python scripts/production_schema_smoke.py

echo "Forward migrations and schema/RLS metadata smoke checks passed."
