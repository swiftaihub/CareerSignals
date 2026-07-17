#!/usr/bin/env bash
set -euo pipefail

release_dir="${1:-$(pwd)}"
expected_source_sha="$(basename "$release_dir")"
[[ "$expected_source_sha" =~ ^[0-9a-f]{40}$ ]] \
  || { echo "Release directory must end in a full lowercase source SHA." >&2; exit 1; }
compose=(docker compose --env-file "$release_dir/release.env" -f "$release_dir/docker-compose.production.yml")

report_service_failure() {
  local service="$1"
  local reason="$2"
  local marker="/tmp/careersignals-health-${expected_source_sha}-${service}.logged"

  echo "$service $reason" >&2
  if [[ ! -e "$marker" ]]; then
    umask 077
    : >"$marker"
    echo "Last $service logs (credentials redacted):" >&2
    "${compose[@]}" logs --no-color --tail 80 "$service" 2>&1 \
      | sed -E \
          -e 's/((motherduck_)?token|password|secret|api[_-]?key)=([^[:space:]&]+)/\1=[REDACTED]/Ig' \
          -e 's/(authorization:[[:space:]]*bearer[[:space:]]+)[^[:space:]]+/\1[REDACTED]/Ig' \
      >&2 || true
  fi
  return 1
}

for service in api worker scheduler reverse-proxy; do
  container_id="$(${compose[@]} ps -q "$service")"
  [[ -n "$container_id" ]] || { report_service_failure "$service" "is not running"; exit 1; }
  state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
  [[ "$state" == "running" ]] || { report_service_failure "$service" "state is $state"; exit 1; }
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
  [[ "$health" == "healthy" ]] || { report_service_failure "$service" "health is $health"; exit 1; }
done

scheduler_count="$(docker ps --filter 'label=com.docker.compose.project=careersignals' --filter 'label=com.docker.compose.service=scheduler' --format '{{.ID}}' | wc -l | tr -d ' ')"
[[ "$scheduler_count" == "1" ]] || { echo "Expected exactly one scheduler; found $scheduler_count" >&2; exit 1; }

health_json="$(curl --fail --silent --show-error --max-time 15 \
  https://careersignals-api.swiftaihub.com/api/health)"
HEALTH_JSON="$health_json" EXPECTED_SOURCE_SHA="$expected_source_sha" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["HEALTH_JSON"])
if payload.get("status") != "ok" or payload.get("source_commit_sha") != os.environ["EXPECTED_SOURCE_SHA"]:
    raise SystemExit("Public API health did not report the target release source SHA.")
PY

echo "API, Worker, single Scheduler, reverse proxy, and source-bound public API health checks passed."
