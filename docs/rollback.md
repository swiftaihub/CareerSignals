# Production rollback

## Scope and status

This runbook defines rollback procedures for the Cloudflare frontend, Oracle application services, and incompatible data changes. It does not claim that any release, retained version, backup, or external production system has been deployed or tested. Verify the real rollback target before every release and record actual results without copying secrets.

Rollback is a controlled release operation, not a substitute for diagnosis. Preserve logs, run identifiers, source SHA, image digest, Worker version, migration state, and the first observed failure before changing traffic or containers.

## Choose the rollback boundary

| Failure | Preferred first action | Data action |
| --- | --- | --- |
| Next.js rendering, assets, base path, callback, or BFF regression | Roll back only the Cloudflare Worker | None if backend/schema remain compatible |
| API/Worker/Scheduler code regression | Roll all backend application services to one previous immutable release | Leave backward-compatible forward migrations in place |
| Frontend/backend contract mismatch | Restore the last known-compatible pair, backend first then frontend | Leave compatible schema in place |
| Bad backward-compatible migration with application failure | Roll back application only if the previous release supports the new schema | Never delete migration history |
| Destructive or incompatible database change | Quiesce all writers and restore a verified pre-change backup into an isolated target | Validate before changing production connections |
| Bad shared Connector publication | Stop Scheduler and Worker; preserve run evidence; restore/republish a validated shared state through an approved data procedure | Application rollback alone does not undo published data |
| Failed personal pipeline | Investigate the failed `run_uuid`; the prior current user partition should remain published | Do not manually change another user's rows |
| Credential exposure | Rotate/revoke at the owning platform and audit access | A code rollback does not unexpose a credential |

## Common preflight

Before either application rollback:

1. Pause new deployments and identify the incident commander/operator.
2. Record the currently active canonical source SHA, frontend Worker deployment/version, backend release directory, image digest, and migration head.
3. Identify one specific known-good target and the evidence that it previously passed health and functional checks.
4. Confirm the target artifact still exists and is immutable.
5. Confirm the current database schema is compatible with the target application. When uncertain, stop and use the database recovery procedure instead of guessing.
6. Confirm secrets and external bindings are still valid; do not copy their values into the incident record.
7. Define success checks and an abort condition before changing traffic.

Do not use `latest`, rebuild an old SHA with new dependencies, or call an unrecorded image tag a rollback. A reproducible rollback uses the retained Worker version or regenerated source manifest, and the backend image digest recorded in its retained `release.env`.

## Backend application rollback

### Validate the target

The default backend script reads the current release's `previous-release` file. Inspect only non-secret release metadata:

```bash
sudo readlink -f /opt/careersignals/current
sudo cat /opt/careersignals/current/previous-release
sudo test -f /opt/careersignals/current/release.env
sudo test -f /opt/careersignals/current/scripts/rollback.sh
```

For an explicit target, require a directory under:

```text
/opt/careersignals/releases/FULL_SOURCE_SHA
```

It must contain its generated `release.env`, Compose file, scripts, and an immutable `CAREERSIGNALS_IMAGE=...@sha256:...` reference. Do not display the service env files during validation.

### Run the checked-in rollback

Roll back to the recorded previous release:

```bash
sudo bash /opt/careersignals/current/scripts/rollback.sh \
  /opt/careersignals
```

Or select an already verified retained release explicitly:

```bash
sudo bash /opt/careersignals/current/scripts/rollback.sh \
  /opt/careersignals \
  /opt/careersignals/releases/REPLACE_WITH_FULL_SOURCE_SHA
```

The script:

1. rejects a target outside the release directory or without release metadata;
2. revalidates root-owned env/TLS controls;
3. validates Compose and pulls the retained immutable image;
4. starts the target API and waits for container health;
5. starts Worker and reverse proxy;
6. stops/removes any existing Scheduler and starts exactly one target Scheduler;
7. runs API, heartbeat, proxy, singleton, and public health checks;
8. advances `current` only after those checks pass.

It deliberately does not reverse database migrations or overwrite runtime environment files.

If target startup or health checks fail after containers change, the script automatically attempts to restart and revalidate the release that was current when rollback began, then leaves `current` pointing to that original release. If both the target rollback and automatic restoration fail, it emits a critical error requiring operator intervention. Preserve the failure output and verify container image digests and health; never infer recovery merely because the symlink still names the original release.

### Verify the backend

```bash
sudo docker compose \
  --env-file /opt/careersignals/current/release.env \
  -f /opt/careersignals/current/docker-compose.production.yml ps

sudo bash /opt/careersignals/current/scripts/health-check.sh \
  /opt/careersignals/current

curl --fail --silent --show-error --max-time 20 \
  https://careersignals-api.swiftaihub.com/api/health
```

Then verify more than liveness:

- all three application services use the intended digest;
- exactly one Scheduler exists and its next run is correct;
- Worker queue age decreases and there are no repeated lock/dbt failures;
- recent Connector source status and shared freshness are acceptable;
- a controlled personal pipeline publishes only its authenticated user's partition;
- Demo, normal-user, Admin, and two-user authorization checks still pass;
- no secrets or raw connector URLs appear in logs.

If those real checks cannot be run, report them as unavailable, not passing.

## Frontend rollback

Record the current and previous Cloudflare deployment/version IDs before every frontend release:

```bash
npx wrangler deployments list \
  --name "REPLACE_WITH_WORKER_NAME"
```

Two supported strategies are available.

### Strategy A: redeploy the previous generated source

This is preferred when the previous source must be rebuilt and revalidated:

1. Select the previous known-good canonical `main` SHA.
2. Manually run the canonical deployment-repository sync in dry-run mode for that SHA and review the generated web manifest/tree.
3. Because production deploys only deployment-repository `main`, sync that reviewed generated tree to deployment `main` through the protected manual workflow; never force-push or hand-edit it.
4. Manually run the web production workflow with the exact SHA recorded in its `SOURCE_MANIFEST.json`.
5. Keep smoke tests enabled and record the new Cloudflare version.

This creates a new deployment from old source. It is not byte-for-byte identical to a retained Worker version if external package resolution or platform behavior has changed, so require the workflow's locked install, build, bundle scan, route verification, and smoke tests.

### Strategy B: move to a retained Cloudflare version

Use this for the fastest reversal when the exact prior Worker version is retained and known good:

```bash
npx wrangler rollback REPLACE_WITH_PREVIOUS_VERSION_ID \
  --name "REPLACE_WITH_WORKER_NAME" \
  --message "Rollback after approved incident review"
```

Review the interactive confirmation. Verify that the target version has the expected routes and bindings and that the dashboard-managed `PASSWORD_RECOVERY_COOKIE_SECRET` remains present. Do not put that secret on the command line.

### Verify the frontend

From the generated web deployment repository:

```bash
APP_ORIGIN=https://jobs.swiftaihub.com \
APP_BASE_PATH=/careersignals \
node scripts/smoke-test.mjs

npx wrangler deployments list \
  --name "REPLACE_WITH_WORKER_NAME"
```

Manually verify:

- `/careersignals` and public pages load over HTTPS with no mixed content;
- assets, metadata, manifest, sitemap, and redirects remain under the base path;
- protected pages redirect internally, without loops or root-path leakage;
- the same-origin BFF reaches backend health;
- registration, login, refresh, logout, callback, recovery, and password update behave correctly;
- route ownership remains limited to `/careersignals` and descendants;
- the client bundle exposes only approved `NEXT_PUBLIC_*` metadata.

Record the active version and canonical source SHA after verification.

## Coordinated frontend/backend rollback

When the contract changed across both layers:

1. Confirm one compatible frontend version, backend digest, and schema state.
2. If the current frontend cannot safely call the target backend, place the application in an approved maintenance state or first deploy a compatibility frontend.
3. Roll back the backend and complete API/queue/single-Scheduler checks.
4. Roll back the frontend and complete base-path/BFF/Auth checks.
5. Run Demo, Admin, normal-user, and two-user isolation smoke tests against the pair.

Do not leave API, Worker, and Scheduler on different source revisions merely to make one symptom disappear. The production workflows and rollback script provide no partial-service mode; restore one coherent backend release. Any emergency ad hoc service isolation is incident containment, not a completed rollout or rollback.

## Forward migrations and database recovery

Application rollback leaves forward migrations in place. This is safe only when the migration was designed to remain backward-compatible with the rollback application.

Never respond to an incident by:

- deleting or editing an already applied migration;
- running `supabase db reset`;
- applying an improvised down migration directly to production;
- restoring over the only production copy without first validating an isolated target;
- changing only one service's shared database credential.

For an incompatible database failure:

1. Block or disable API mutations through the approved maintenance mechanism.
2. Stop Scheduler first, then Worker, then any remaining API writers.
3. Record the database project, migration head, active release, affected run UUIDs, and recovery-point identifier without recording credentials.
4. Restore the verified pre-migration backup into a new isolated database/project.
5. Apply only the migrations required by the selected known-good application.
6. Validate schema shape, RLS, Auth triggers, Demo seed, Admin authorization, two-user isolation, queue claims/locks, and current-result uniqueness.
7. Validate or reconnect a MotherDuck state compatible with the selected release; PostgreSQL restore alone may not restore analytical inputs.
8. Rotate any temporary recovery credentials.
9. Update `DATABASE_URL` atomically in API, Worker, and Scheduler root-owned env files. Update migration targeting separately if future operations need it.
10. Recreate API and verify read/auth behavior before resuming Worker, then resume exactly one Scheduler.
11. Monitor queue age, shared freshness, publication, database connections, and errors before ending maintenance.

Keep the failed environment isolated for investigation when policy and cost allow. Do not point production traffic to the restored target until the validation suite has actually run.

## Shared and per-user data incidents

### Bad shared refresh

Stop the singleton Scheduler to prevent another scheduled enqueue, then stop Worker execution. Preserve the `connector_run_uuid`, source-level results, acquisition audit, dbt artifacts/log identifiers, and publication timestamps. Determine whether the error is acquisition, MotherDuck/dbt, or PostgreSQL publication.

Restore or republish only a previously validated shared partition through a reviewed data operation. The application release rollback script does not undo a shared publication. Resume Worker first under observation, then Scheduler only after freshness and source status are coherent.

### Failed personal refresh

Personal publication is designed to leave the prior current result in place when a new run fails. Preserve and inspect the user's failed `run_uuid` and source `connector_run_uuid`. Do not manually flip `is_current` flags across users, accept a tenant UUID from an untrusted request, or run an arbitrary dbt selector. Escalate any evidence that the prior partition was not preserved as a tenant-isolation incident.

## Secret incidents are rotation events

If a credential may have appeared in Git, a bundle, image layer, workflow log, process dump, URL, or issue:

1. identify the variable name and owning platform without copying the value;
2. revoke/rotate it at the provider;
3. update only the approved secret store or Oracle service file;
4. recreate the consuming service and verify access;
5. audit provider, GitHub, SSH, and application logs;
6. scan current artifacts and Git history;
7. decide whether history cleanup and downstream clone invalidation are required.

Deleting a file or rolling back code does not revoke an exposed secret.

## Closeout record

Record these independently:

```text
Incident start/end time
Observed symptom and affected scope
Previous and resulting canonical source SHA
Previous and resulting Worker deployment/version
Previous and resulting backend release directory/image digest
Database migration head and recovery point used, if any
Checks actually run and their results
Checks unavailable or skipped
Remaining monitoring and owner actions
```

Use precise status language: `rollback procedure executed`, `health checks passed`, and `functional smoke tests passed` are separate claims. Do not state that production is recovered solely because a script exited successfully.
