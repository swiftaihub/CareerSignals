# Production runbook

## Preflight

Record the intended canonical `main` SHA. Confirm no uncommitted code is part of the release and both deployment manifests record that SHA. Confirm the previous Worker version, backend release directory, and image digest are available.

Review:

- canonical and deployment secret scans;
- pytest skips and non-production RLS/integration results;
- frontend test/lint/typecheck/build and OpenNext build;
- dbt dependency/compile and staged shared/user build results;
- ARM64 image build and Compose validation;
- migration list and verified recovery point if schema changes are planned;
- Cloudflare routes, DNS proxy status, Full (strict), Supabase Site/Redirect URLs;
- Oracle env/TLS ownership/mode and exactly one Scheduler;
- canonical `production` environment approval and `DEPLOY_REPOSITORIES_TOKEN` availability for both sync dry run and push;
- the exact-hash root-owned Oracle installer at `/usr/local/sbin/careersignals-install-release` and its reviewed sudoers rule.

## Backend release

Run the manual backend workflow first so the BFF target is ready before frontend traffic changes. There are no partial service toggles: API, Worker, and the singleton Scheduler deploy as one release from the same image digest. The installer refuses to overwrite a release directory for the same source SHA and attempts to restore the previously current application release if the new application fails health checks. Keep migrations disabled unless explicitly approved; automatic application restoration does not reverse them.

Afterward verify:

```bash
curl --fail https://careersignals-api.swiftaihub.com/api/health
```

On Oracle:

```bash
sudo bash /opt/careersignals/current/scripts/health-check.sh /opt/careersignals/current
sudo docker compose \
  --env-file /opt/careersignals/current/release.env \
  -f /opt/careersignals/current/docker-compose.production.yml ps
```

Require the public health JSON to report both `status=ok` and the exact requested `source_commit_sha`; the workflow enforces this. Record source SHA and image digest. Confirm Worker queue progress and that only the authenticated user partition is published. Confirm one Scheduler and the next configured refresh occurrence.

## Frontend release

Run the manual web workflow using the same canonical SHA. Production smoke cannot be disabled. The Cloudflare token is exposed only to Wrangler secret-inventory, deployment-list, and deploy steps, after tests and builds. Record the new Cloudflare version and retain the previous version.

Require public `2xx`, guarded `3xx` to the internal base-path login, code-less callback `3xx` to the internal forgot-password page, BFF health JSON with `status=ok` and the same canonical SHA, and no mixed content/base-path leakage. Then verify assets/canonical metadata and execute real registration/login/refresh/logout/recovery/password-update tests with approved non-production accounts in production.

## Authorization and isolation smoke suite

Use Demo, Admin, a normal user, and two dedicated isolation users. Verify:

- unauthenticated route protection;
- pending, expired, and suspended account behavior;
- Demo is fixed and read-only;
- normal users cannot call Admin APIs or global connector controls;
- User A cannot see User B jobs, Dashboard, config, application state, or pipeline results;
- a personal pipeline updates only the authenticated partition;
- no request accepts an arbitrary tenant UUID or dbt selector.

If suitable test accounts or safe validation data are unavailable, mark these tests unavailable—not passed.

## Forward migrations

Before enabling `apply_migrations`:

1. create and verify a production backup/recovery point;
2. create the corresponding root-owned Oracle backup marker;
3. review forward migrations and compatibility with the currently running application;
4. ensure `/opt/careersignals/env/migration.env` is root-owned mode 600 and references the expected project;
5. review the redacted `supabase db push --dry-run` output;
6. apply only forward migrations;
7. require the metadata smoke to find all 25 reviewed tables with RLS enabled and forced, the exact 30-name active public-policy inventory, and the reviewed minimum table/role/command/expression invariants;
8. deploy backward-compatible application images.

The metadata smoke does not execute as two real users and cannot prove row isolation. Run the live two-user RLS/Auth/application suite separately and report it unavailable rather than passed if credentials or safe data are missing. The direct database URL is passed to the Supabase CLI as a process argument; restrict host logins, avoid broad process listings during migration, and use a tested host `/proc` policy such as `hidepid=2` where compatible. Never run `supabase db reset` or delete migration history in production.

## Incident actions

### Frontend regression

Redeploy the previous known-good generated commit or retained Worker version. Run base-path/BFF/Auth smoke tests and record the active version.

### Backend application regression

Run the rollback script for the previous release. It pulls immutable images, replaces API/Worker/one Scheduler, preserves env files, and does not reverse migrations. Verify public API and queue health.

### Database incompatibility

Stop Writer and Scheduler services. Do not delete forward migrations. Restore the verified pre-migration backup into an isolated target, validate it, then change production connection values through an approved maintenance procedure.

### Credential exposure

Identify affected variable names without copying values. Rotate them at the owning platform, revoke old credentials, audit access/workflow logs, scan Git history and deployment artifacts, and decide whether history cleanup is required. A currently deleted secret remains compromised if it was committed.

### Stuck queue run

Inspect redacted internal run status and database locks. Do not enqueue arbitrary tenants or manually modify result partitions. Because leases/stale-run reaping are limited, resolve the underlying process/database condition before a controlled state repair.

## Routine operations

- Review API/Worker/Scheduler health and connector freshness.
- Review Supabase connection counts across process pools.
- Confirm Scheduler count remains one after host/runtime changes.
- Update Cloudflare and Oracle IP/firewall policies when provider ranges change.
- Patch pinned base images/adapters after staging ARM64/OpenNext validation.
- Test both rollback procedures periodically.
- Rotate secrets on policy, not per deployment; record dates without values.
- Keep GitHub deployment Environments manual and reviewer-protected.
