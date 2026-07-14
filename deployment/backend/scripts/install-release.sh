#!/usr/bin/env bash
set -Eeuo pipefail

deploy_root="${1:?deploy root is required}"
release_id="${2:?full source SHA is required}"
archive="${3:?release archive is required}"
image_ref="${4:?immutable image reference is required}"
apply_migrations="${5:-false}"
backup_reference="${6:-}"

[[ "$deploy_root" == "/opt/careersignals" ]] \
  || { echo "Deploy root must be exactly /opt/careersignals." >&2; exit 1; }
[[ "$release_id" =~ ^[0-9a-f]{40}$ ]] \
  || { echo "Release ID must be a full lowercase source SHA." >&2; exit 1; }
[[ "$archive" == "/tmp/release-$release_id.tar.gz" && -f "$archive" && ! -L "$archive" ]] \
  || { echo "Release archive path or type is invalid." >&2; exit 1; }
[[ "$image_ref" =~ ^ghcr\.io/[A-Za-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] \
  || { echo "Image reference must be an immutable GHCR digest." >&2; exit 1; }
[[ "$apply_migrations" == "true" || "$apply_migrations" == "false" ]] \
  || { echo "apply_migrations must be true or false." >&2; exit 1; }
if [[ "$apply_migrations" == "true" ]]; then
  [[ "$backup_reference" =~ ^[A-Za-z0-9._-]+$ ]] \
    || { echo "A safe verified backup reference is required for migrations." >&2; exit 1; }
else
  [[ -z "$backup_reference" ]] \
    || { echo "backup_reference must be empty when migrations are disabled." >&2; exit 1; }
fi

install -d -m 755 -o root -g root \
  "$deploy_root" "$deploy_root/releases" "$deploy_root/backups"

# Copy the upload into a root-owned location before validating it. This keeps
# the unprivileged upload path from changing between validation and extraction.
trusted_archive="$(mktemp -p "$deploy_root/backups" ".release-$release_id.XXXXXX.tar.gz")"
staging_dir=""
cleanup_staging="true"
cleanup() {
  if [[ "$cleanup_staging" == "true" && -n "${staging_dir:-}" && "$staging_dir" == "$deploy_root"/releases/.staging-* ]]; then
    rm -rf -- "$staging_dir"
  fi
  if [[ -n "${trusted_archive:-}" && "$trusted_archive" == "$deploy_root"/backups/.release-"$release_id".*.tar.gz ]]; then
    rm -f -- "$trusted_archive"
  fi
}
trap cleanup EXIT
archive_size="$(stat -c '%s' "$archive")"
[[ "$archive_size" =~ ^[0-9]+$ && "$archive_size" -le $((256 * 1024 * 1024)) ]] \
  || { echo "Release archive exceeds the allowed compressed size." >&2; exit 1; }
install -m 600 -o root -g root -- "$archive" "$trusted_archive"
trusted_archive_size="$(stat -c '%s' "$trusted_archive")"
[[ "$trusted_archive_size" =~ ^[0-9]+$ && "$trusted_archive_size" -le $((256 * 1024 * 1024)) ]] \
  || { echo "Trusted release archive exceeds the allowed compressed size." >&2; exit 1; }

# The fixed, root-owned installer validates archive member types before extraction.
python3 - "$trusted_archive" <<'PY'
import pathlib
import sys
import tarfile

archive = sys.argv[1]
required = {
    "SOURCE_MANIFEST.json",
    "docker-compose.production.yml",
    "scripts/health-check.sh",
    "scripts/rollback.sh",
    "scripts/validate-source-manifest.py",
    "scripts/verify-environment.sh",
}
names: set[str] = set()
kinds: dict[str, str] = {}
total_size = 0
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    if len(members) > 10_000:
        raise SystemExit("Release archive contains too many members.")
    for member in members:
        normalized = pathlib.PurePosixPath(member.name)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise SystemExit("Release archive contains an unsafe path.")
        if not (member.isfile() or member.isdir()):
            raise SystemExit("Release archive contains a link or special file.")
        total_size += member.size
        name = normalized.as_posix().removeprefix("./")
        if name in names:
            raise SystemExit("Release archive contains a duplicate member path.")
        names.add(name)
        kinds[name] = "file" if member.isfile() else "directory"
    if total_size > 512 * 1024 * 1024:
        raise SystemExit("Release archive expands beyond the allowed size.")
missing = sorted(required - names)
if missing:
    raise SystemExit("Release archive is missing required files.")
if any(kinds[name] != "file" for name in required):
    raise SystemExit("Release archive contains a required path with the wrong type.")
PY

release_dir="$deploy_root/releases/$release_id"
[[ ! -e "$release_dir" && ! -L "$release_dir" ]] \
  || { echo "Release already exists; immutable source SHAs cannot be redeployed in place." >&2; exit 1; }

previous_release=""
if [[ -e "$deploy_root/current" || -L "$deploy_root/current" ]]; then
  [[ -L "$deploy_root/current" ]] \
    || { echo "Current release pointer is not a symbolic link." >&2; exit 1; }
  previous_release="$(readlink -f "$deploy_root/current")"
  [[ "$previous_release" =~ ^/opt/careersignals/releases/[0-9a-f]{40}$ && -d "$previous_release" && ! -L "$previous_release" ]] \
    || { echo "Current release pointer is invalid." >&2; exit 1; }
fi

staging_dir="$(mktemp -d -p "$deploy_root/releases" ".staging-$release_id.XXXXXX")"

tar --extract --gzip --file "$trusted_archive" --directory "$staging_dir" --no-same-owner --no-same-permissions
chown -R root:root "$staging_dir"
chmod -R u=rwX,go=rX "$staging_dir"

python3 "$staging_dir/scripts/validate-source-manifest.py" \
  --target backend \
  --expected-sha "$release_id" \
  --manifest "$staging_dir/SOURCE_MANIFEST.json"
bash "$staging_dir/scripts/verify-environment.sh" "$deploy_root"

cat >"$staging_dir/release.env" <<EOF
CAREERSIGNALS_IMAGE=$image_ref
CAREERSIGNALS_ENV_DIR=$deploy_root/env
CAREERSIGNALS_TLS_DIR=$deploy_root/tls
CADDY_IMAGE=caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648
EOF
chmod 644 "$staging_dir/release.env"
if [[ -n "$previous_release" ]]; then
  printf '%s\n' "$previous_release" >"$staging_dir/previous-release"
  chmod 644 "$staging_dir/previous-release"
fi

staging_compose=(docker compose --env-file "$staging_dir/release.env" -f "$staging_dir/docker-compose.production.yml")
"${staging_compose[@]}" config --quiet
"${staging_compose[@]}" pull

if [[ "$apply_migrations" == "true" ]]; then
  # Production migrations must be backward-compatible with the still-running prior release.
  bash "$staging_dir/scripts/apply-migrations.sh" \
    "$deploy_root" "$staging_dir" "$backup_reference" "$image_ref"
fi

mv -- "$staging_dir" "$release_dir"
cleanup_staging="false"
compose=(docker compose --env-file "$release_dir/release.env" -f "$release_dir/docker-compose.production.yml")

restore_previous() {
  if [[ -n "$previous_release" ]]; then
    echo "Deployment failed; attempting to restore the previous application release." >&2
    bash "$previous_release/scripts/rollback.sh" "$deploy_root" "$previous_release"
  else
    echo "Initial deployment failed; stopping the incomplete application stack." >&2
    "${compose[@]}" stop
  fi
}

on_deploy_error() {
  local status=$?
  trap - ERR
  set +e
  restore_previous
  local restore_status=$?
  set -e
  if [[ "$restore_status" != "0" ]]; then
    echo "CRITICAL: automatic application restoration also failed; operator intervention is required." >&2
  fi
  exit "$status"
}
trap on_deploy_error ERR

# A production release is an atomic API + Worker + single-Scheduler unit.
"${compose[@]}" up -d --no-deps api
for _ in {1..30}; do
  api_id="$("${compose[@]}" ps -q api)"
  [[ -n "$api_id" ]] && [[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$api_id")" == "healthy" ]] && break
  sleep 5
done
api_id="$("${compose[@]}" ps -q api)"
[[ -n "$api_id" ]] && [[ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$api_id")" == "healthy" ]]
"${compose[@]}" up -d --no-deps reverse-proxy
"${compose[@]}" up -d --no-deps worker
"${compose[@]}" stop scheduler >/dev/null 2>&1 || true
"${compose[@]}" rm -f scheduler >/dev/null 2>&1 || true
"${compose[@]}" up -d --no-deps scheduler

release_healthy="false"
for _ in {1..24}; do
  if bash "$release_dir/scripts/health-check.sh" "$release_dir"; then
    release_healthy="true"
    break
  fi
  sleep 5
done
[[ "$release_healthy" == "true" ]]

ln -sfnT "$release_dir" "$deploy_root/current"
trap - ERR
echo "Release $release_id is healthy and current."
