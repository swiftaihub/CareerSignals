# CareerSignals backend deployment repository

This private repository is generated from `swiftaihub/CareerSignals`. It is an immutable deployment input, not a business-development repository. `SOURCE_MANIFEST.json` identifies the canonical `main` branch and full source SHA. Make code or deployment-template changes in the canonical repository and regenerate this repository.

The intended production target is an Oracle Cloud Ampere A1 Paid As You Go VM (`linux/arm64`). This repository does not prove that it has been deployed. One immutable application image starts three separate processes:

```text
api        FastAPI on the private Docker network at port 8000
worker     connector acquisition and user pipeline queue consumer
scheduler  exactly one global enqueue scheduler
```

Caddy is the only service publishing host ports 80 and 443. `careersignals-api.swiftaihub.com` is proxied by Cloudflare to the Oracle reserved public IP. Use Cloudflare **Full (strict)** TLS with an Origin certificate or a publicly trusted certificate; never Flexible SSL.

## Required GitHub production environment

Secrets:

```text
ORACLE_SSH_PRIVATE_KEY
ORACLE_SSH_KNOWN_HOSTS
```

Variables:

```text
ORACLE_HOST
ORACLE_SSH_USER
ORACLE_DEPLOY_PATH=/opt/careersignals
GHCR_IMAGE=ghcr.io/OWNER/IMAGE
```

The SSH key should be restricted to the dedicated deployment account. Store a pinned Oracle host-key line in `ORACLE_SSH_KNOWN_HOSTS`; do not replace host verification with an unchecked `ssh-keyscan` during deployment. The root Docker client on Oracle must already be logged in to GHCR with a read-only package token if the image is private. GitHub uses its scoped `GITHUB_TOKEN` only to publish the image. `ORACLE_DEPLOY_PATH` must be exactly `/opt/careersignals`.

## One-time Oracle preparation

Install Docker Engine with the Compose plugin, the exact Supabase CLI version recorded in `supabase-cli.version`, and normal host security updates. The migration script refuses a CLI version mismatch. Python dependencies are exact-pinned in `requirements.lock`; both Python stages and the multi-platform Caddy manifest that includes ARM64 are digest-pinned. Review lock/digest updates and validate an ARM64 build before syncing them. Create:

```text
/opt/careersignals/env/api.env
/opt/careersignals/env/worker.env
/opt/careersignals/env/scheduler.env
/opt/careersignals/env/migration.env      # only if workflows apply migrations
/opt/careersignals/tls/origin.pem
/opt/careersignals/tls/origin.key
/opt/careersignals/backups/
```

All env and TLS files must be regular, non-symlink files owned by `root:root` with mode `600`. The deployment workflow verifies them and never uploads, downloads, overwrites, or prints them.

Install the reviewed release helper once, and update it manually whenever its exact hash changes:

```bash
sha256sum scripts/install-release.sh
sudo install -m 755 -o root -g root \
  scripts/install-release.sh \
  /usr/local/sbin/careersignals-install-release
sudo sha256sum /usr/local/sbin/careersignals-install-release
sudo stat -c '%U:%G %a' /usr/local/sbin/careersignals-install-release
```

The hashes must match and metadata must be `root:root 755`. Use `sudo visudo -f /etc/sudoers.d/careersignals-deploy` to grant only the dedicated account this command, then validate the fragment:

```sudoers
REPLACE_WITH_DEPLOYMENT_USER ALL=(root) NOPASSWD: /usr/local/sbin/careersignals-install-release *
```

```bash
sudo chmod 440 /etc/sudoers.d/careersignals-deploy
sudo visudo -cf /etc/sudoers.d/careersignals-deploy
```

The workflow compares the installed helper's exact hash before every release and never self-updates or invokes the bundle copy as the installer. This is still root-equivalent deployment authority: the helper runs Docker and reviewed release scripts as root. Protect the SSH key, canonical sync, generated repository, workflow, and GitHub `production` environment as root-authority boundaries; do not grant the account Docker-group membership or broad `sudo`.

Use least privilege for application secret distribution (this does not reduce the deployment account's root-equivalent release authority):

- `api.env`: PostgreSQL, Supabase service/JWT configuration, Demo secret, CORS origin, API quota/freshness settings.
- `worker.env`: PostgreSQL, MotherDuck, dbt, selected connector credentials, pipeline concurrency/polling.
- `scheduler.env`: PostgreSQL plus cron, timezone, and trigger mode only.
- `migration.env`: direct production database URL and non-secret Supabase project reference only for migration operations.

Initial production values must include:

```env
CAREERSIGNAL_SAAS_MODE=true
CAREERSIGNAL_ENVIRONMENT=production
CAREERSIGNAL_DATA_MODE=postgres
CORS_ORIGINS=https://jobs.swiftaihub.com
SUPABASE_JWT_AUDIENCE=authenticated
DEMO_USER_UUID=00000000-0000-4000-8000-000000000020
LOG_LEVEL=INFO
MOTHERDUCK_DATABASE=CareerSignal
DBT_TARGET=prod
CAREERSIGNAL_RUN_DBT=true
CAREERSIGNAL_WRITE_DEBUG_JSON=false
USER_PIPELINE_MAX_CONCURRENCY=1
CONNECTOR_REFRESH_CRON=0 7,16,21 * * *
CONNECTOR_REFRESH_TIMEZONE=America/New_York
CONNECTOR_REFRESH_TRIGGER_MODE=scheduled
```

Do not put `/careersignals` in `CORS_ORIGINS`; CORS values are origins, not URLs with paths. `DEMO_SESSION_SECRET` must contain at least 32 characters. `JOB_SOURCES` must be `all` or an explicit comma-separated subset of `adzuna`, `serpapi`, `greenhouse`, `lever`, and `usajobs`; the verifier requires the corresponding credentials/identifiers for every selected source. Do not give API or Scheduler the Worker’s connector/MotherDuck credentials. `SUPABASE_SERVICE_ROLE_KEY` is the canonical backend secret name; `SUPABASE_SECRET_KEY` is not a runtime alias.

Create a Cloudflare Origin certificate for `careersignals-api.swiftaihub.com`, place it in the TLS paths above, and keep Cloudflare proxying enabled. Oracle Security Lists, Network Security Groups, and the host firewall should permit only:

```text
22/tcp   restricted administration/deployment sources
80/tcp   Cloudflare/or certificate validation as required
443/tcp  Cloudflare
```

Never expose port 8000 publicly. Restrict ports 80/443 to Cloudflare published IP ranges when operationally feasible and maintain that allowlist.

## Manual production deployment

1. Confirm the recorded source SHA is on canonical `CareerSignals/main`.
2. Confirm a recoverable database backup or recovery point before a schema change.
3. Open **Actions → Deploy CareerSignals backend to production → Run workflow** on this repository's `main` branch.
4. Enter the exact canonical source SHA.
5. Confirm `/usr/local/sbin/careersignals-install-release` is the exact reviewed hash expected by this generated revision; if it changed, an owner must update the root-owned helper before rerunning the workflow.
6. Keep `apply_migrations=false` unless a forward migration is intentionally approved. For a migration, create a `root:root` mode-`600` marker named `/opt/careersignals/backups/verified-<backup_reference>` and enter that reference. The migration gate performs a dry run, applies only forward migrations, then verifies 25 RLS-enabled/forced public tables, the exact 30-name public-policy inventory, and reviewed minimum metadata invariants.
7. Review pytest skips, dbt compile/parse, ARM64 image digest, Oracle health checks, public health source SHA, and the job summary.

The workflow is `workflow_dispatch` only. It builds and pushes `sha-<source SHA>`, refuses to overwrite an existing source-SHA tag or release directory, deploys the resulting digest, uploads only non-secret release definitions, and preserves prior releases for rollback. It never uses `latest` as the release identity. There are no partial service inputs: API, Worker, and Scheduler are one atomic application release. If deployment fails after service mutation begins, the installer attempts to restore the previously current release; an initial failure stops the incomplete stack. Migrations are not reversed automatically.

The metadata migration smoke does not execute requests as two real users and does not replace the live two-user RLS, Demo, Admin, or tenant-isolation suite. Also note that `supabase db push --db-url` places the direct URL in process arguments. Restrict host logins, avoid process-list diagnostics during migration, and consider a tested OS `/proc` policy such as `hidepid=2`; rotate the database credential if argument exposure is suspected.

## Health checks

On Oracle:

```bash
sudo bash /opt/careersignals/current/scripts/health-check.sh /opt/careersignals/current
sudo docker compose \
  --env-file /opt/careersignals/current/release.env \
  -f /opt/careersignals/current/docker-compose.production.yml ps
```

Externally:

```bash
curl --fail https://careersignals-api.swiftaihub.com/api/health
```

The public response must contain `status=ok` and the exact requested `source_commit_sha`; the workflow parses and enforces both. The release script also requires healthy API, Worker heartbeat, Scheduler heartbeat, reverse proxy, and exactly one Scheduler container. API liveness and provenance alone do not prove queue processing, MotherDuck publication, or tenant isolation; monitor connector/user pipeline run freshness separately.

## Rollback

Each release records the previous release directory and an immutable image digest. Roll back without changing database migration history:

```bash
sudo bash /opt/careersignals/current/scripts/rollback.sh /opt/careersignals
```

Or name a verified release explicitly:

```bash
sudo bash /opt/careersignals/current/scripts/rollback.sh \
  /opt/careersignals \
  /opt/careersignals/releases/FULL_SOURCE_SHA
```

The script runs `docker compose pull` and `docker compose up -d`, replaces the Scheduler rather than scaling it, runs health checks, and advances the `current` symlink only after success. If rollback health checks fail after containers change, it attempts to restore the release that was current when rollback began and reports a critical error if restoration also fails. Do not delete forward migrations to roll back. Application releases must remain compatible with the current schema. For an incompatible database failure, stop writers and restore a verified pre-migration backup into an isolated target before changing production connection values.

## Secret rotation and troubleshooting

Rotate Oracle env values in place under a maintenance procedure, retain mode/ownership, then recreate only the consuming service. Rotate the SSH key in both Oracle `authorized_keys` and GitHub. Rotate the Cloudflare Origin certificate by staging both files atomically and recreating Caddy. Never put secret values into workflow inputs, issue comments, Compose files, or diagnostic output.

Common failures:

- ARM64 build fails: identify the native wheel/package and pin a compatible version; never substitute an unverified amd64 image.
- API unhealthy: inspect redacted application logs and validate only API env requirements.
- Worker unhealthy: verify its heartbeat, PostgreSQL, MotherDuck, dbt `prod` target, selected connector configuration, and outbound TLS.
- Scheduler count is not one: stop/remove duplicate Compose projects before continuing.
- Migration refused: verify the root-owned backup marker, `migration.env`, direct database hostname/project reference, CLI version, and dry-run output.
- TLS fails through Cloudflare: verify DNS proxying, Full (strict), certificate hostname/validity, and Oracle/host firewall rules.

Do not print Docker environments or raw connector exceptions; connector query parameters can contain credentials.
