#!/usr/bin/env bash
set -euo pipefail

deploy_root="${1:-/opt/careersignals}"
[[ "$deploy_root" == "/opt/careersignals" ]] \
  || { echo "Environment validation failed: deploy root must be /opt/careersignals" >&2; exit 1; }
env_dir="$deploy_root/env"
tls_dir="$deploy_root/tls"

fail() {
  echo "Environment validation failed: $1" >&2
  exit 1
}

verify_file() {
  local file="$1" owner mode
  [[ -f "$file" && ! -L "$file" ]] || fail "required restricted file is missing"
  owner="$(stat -c '%U:%G' "$file")"
  mode="$(stat -c '%a' "$file")"
  [[ "$owner" == "root:root" ]] || fail "restricted files must be owned by root:root"
  [[ "$mode" == "600" ]] || fail "restricted files must have mode 600"
}

read_env_value() {
  local file="$1" key="$2" output_name="$3" line parsed_value="" found="false"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ "$line" == "$key="* ]] || continue
    [[ "$found" == "false" ]] || fail "$(basename "$file") contains a duplicate $key entry"
    parsed_value="${line#*=}"
    found="true"
  done <"$file"
  [[ "$found" == "true" ]] || fail "$key is missing from $(basename "$file")"
  printf -v "$output_name" '%s' "$parsed_value"
}

require_value() {
  local file="$1" key="$2" value=""
  read_env_value "$file" "$key" value
  [[ -n "$value" && "$value" != REPLACE_WITH_* ]] \
    || fail "$key is empty or still a placeholder in $(basename "$file")"
}

require_exact() {
  local file="$1" key="$2" expected="$3" value=""
  read_env_value "$file" "$key" value
  [[ "$value" == "$expected" ]] \
    || fail "$key has not been set to its approved production value in $(basename "$file")"
}

forbid_key() {
  local file="$1" key="$2"
  if grep -Eq "^${key}=" "$file"; then
    fail "$key must not be distributed to $(basename "$file")"
  fi
}

for name in api worker scheduler; do
  verify_file "$env_dir/$name.env"
done

api_env="$env_dir/api.env"
require_exact "$api_env" CAREERSIGNAL_SAAS_MODE true
require_exact "$api_env" CAREERSIGNAL_ENVIRONMENT production
require_exact "$api_env" CAREERSIGNAL_DATA_MODE postgres
require_value "$api_env" DATABASE_URL
require_value "$api_env" SUPABASE_URL
require_value "$api_env" SUPABASE_SERVICE_ROLE_KEY
require_exact "$api_env" SUPABASE_JWT_AUDIENCE authenticated
require_exact "$api_env" DEMO_USER_UUID 00000000-0000-4000-8000-000000000020
require_value "$api_env" DEMO_SESSION_SECRET
require_exact "$api_env" CORS_ORIGINS https://jobs.swiftaihub.com
require_exact "$api_env" LOG_LEVEL INFO
demo_secret=""
read_env_value "$api_env" DEMO_SESSION_SECRET demo_secret
[[ ${#demo_secret} -ge 32 ]] || fail "DEMO_SESSION_SECRET must contain at least 32 characters"
for key in MOTHERDUCK_TOKEN ADZUNA_APP_KEY SERPAPI_API_KEY USAJOBS_API_KEY ADMIN_BOOTSTRAP_PASSWORD; do
  forbid_key "$api_env" "$key"
done

worker_env="$env_dir/worker.env"
require_exact "$worker_env" CAREERSIGNAL_SAAS_MODE true
require_exact "$worker_env" CAREERSIGNAL_ENVIRONMENT production
require_exact "$worker_env" CAREERSIGNAL_DATA_MODE postgres
require_value "$worker_env" DATABASE_URL
require_value "$worker_env" MOTHERDUCK_TOKEN
require_exact "$worker_env" MOTHERDUCK_DATABASE CareerSignal
require_exact "$worker_env" DBT_TARGET prod
require_exact "$worker_env" CAREERSIGNAL_RUN_DBT true
require_exact "$worker_env" CAREERSIGNAL_WRITE_DEBUG_JSON false
require_exact "$worker_env" USER_PIPELINE_MAX_CONCURRENCY 1
require_value "$worker_env" JOB_SOURCES
job_sources=""
read_env_value "$worker_env" JOB_SOURCES job_sources
[[ "$job_sources" =~ ^(all|((adzuna|serpapi|greenhouse|lever|usajobs)(,(adzuna|serpapi|greenhouse|lever|usajobs))*))$ ]] \
  || fail "JOB_SOURCES must contain only explicitly approved real production sources"
source_enabled() {
  local source="$1"
  [[ "$job_sources" == "all" || ",$job_sources," == *",$source,"* ]]
}
if source_enabled adzuna; then
  require_value "$worker_env" ADZUNA_APP_ID
  require_value "$worker_env" ADZUNA_APP_KEY
fi
if source_enabled serpapi; then
  require_value "$worker_env" SERPAPI_API_KEY
fi
if source_enabled greenhouse; then
  require_value "$worker_env" GREENHOUSE_COMPANY_TOKENS
fi
if source_enabled lever; then
  require_value "$worker_env" LEVER_COMPANY_SITES
fi
if source_enabled usajobs; then
  require_value "$worker_env" USAJOBS_USER_AGENT
  require_value "$worker_env" USAJOBS_API_KEY
fi
for key in SUPABASE_SERVICE_ROLE_KEY DEMO_SESSION_SECRET ADMIN_BOOTSTRAP_PASSWORD; do
  forbid_key "$worker_env" "$key"
done

scheduler_env="$env_dir/scheduler.env"
require_exact "$scheduler_env" CAREERSIGNAL_SAAS_MODE true
require_exact "$scheduler_env" CAREERSIGNAL_ENVIRONMENT production
require_value "$scheduler_env" DATABASE_URL
require_exact "$scheduler_env" CONNECTOR_REFRESH_CRON "0 7,16,21 * * *"
require_exact "$scheduler_env" CONNECTOR_REFRESH_TIMEZONE America/New_York
require_exact "$scheduler_env" CONNECTOR_REFRESH_TRIGGER_MODE scheduled
require_exact "$scheduler_env" LOG_LEVEL INFO
for key in SUPABASE_SERVICE_ROLE_KEY MOTHERDUCK_TOKEN DEMO_SESSION_SECRET SCHEDULER_INTERNAL_SECRET ADZUNA_APP_KEY SERPAPI_API_KEY USAJOBS_API_KEY; do
  forbid_key "$scheduler_env" "$key"
done

verify_file "$tls_dir/origin.pem"
verify_file "$tls_dir/origin.key"

echo "Restricted production environment files, exact service settings, least-privilege boundaries, and TLS material are valid."
