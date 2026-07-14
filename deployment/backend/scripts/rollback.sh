#!/usr/bin/env bash
set -Eeuo pipefail

deploy_root="${1:-/opt/careersignals}"
target_release="${2:-}"

[[ "$deploy_root" == "/opt/careersignals" ]] \
  || { echo "Deploy root must be exactly /opt/careersignals." >&2; exit 1; }
[[ -L "$deploy_root/current" ]] \
  || { echo "Current release pointer is missing or invalid." >&2; exit 1; }
original_release="$(readlink -f "$deploy_root/current")"
[[ "$original_release" =~ ^/opt/careersignals/releases/[0-9a-f]{40}$ && -d "$original_release" && ! -L "$original_release" ]] \
  || { echo "Current release pointer is outside the release directory." >&2; exit 1; }

if [[ -z "$target_release" ]]; then
  [[ -f "$original_release/previous-release" && ! -L "$original_release/previous-release" ]] \
    || { echo "No previous release is recorded." >&2; exit 1; }
  target_release="$(<"$original_release/previous-release")"
fi

[[ ! -L "$target_release" ]] \
  || { echo "Rollback target must not be a symbolic link." >&2; exit 1; }
target_release="$(readlink -f -- "$target_release")"
[[ "$target_release" =~ ^/opt/careersignals/releases/[0-9a-f]{40}$ && -d "$target_release" && ! -L "$target_release" ]] \
  || { echo "Rollback target is outside the release directory or missing." >&2; exit 1; }
[[ -f "$target_release/release.env" && ! -L "$target_release/release.env" ]] \
  || { echo "Rollback target has no immutable release metadata." >&2; exit 1; }

start_release() {
  local release="$1" api_id="" release_healthy="false"
  local -a compose=(docker compose --env-file "$release/release.env" -f "$release/docker-compose.production.yml")

  python3 "$release/scripts/validate-source-manifest.py" \
    --target backend \
    --expected-sha "$(basename "$release")" \
    --manifest "$release/SOURCE_MANIFEST.json"
  bash "$release/scripts/verify-environment.sh" "$deploy_root"
  "${compose[@]}" config --quiet
  "${compose[@]}" pull
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

  for _ in {1..24}; do
    if bash "$release/scripts/health-check.sh" "$release"; then
      release_healthy="true"
      break
    fi
    sleep 5
  done
  [[ "$release_healthy" == "true" ]]
}

restore_original() {
  local failed_status=$?
  trap - ERR
  if [[ "$target_release" == "$original_release" ]]; then
    echo "Rollback target failed its health checks; no alternate release is available." >&2
    exit "$failed_status"
  fi

  echo "Rollback failed; attempting to restore the release that was current when rollback began." >&2
  set +e
  (
    set -Eeuo pipefail
    trap - ERR
    start_release "$original_release"
  )
  local restore_status=$?
  set -e
  if [[ "$restore_status" == "0" ]]; then
    ln -sfnT "$original_release" "$deploy_root/current"
    echo "The original application release was restored." >&2
  else
    echo "CRITICAL: rollback and restoration both failed; operator intervention is required." >&2
  fi
  exit "$failed_status"
}
trap restore_original ERR

start_release "$target_release"
ln -sfnT "$target_release" "$deploy_root/current"
trap - ERR

echo "Rolled back application services to $(basename "$target_release"). Database migrations were not reversed."
