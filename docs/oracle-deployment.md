# Oracle Ampere A1 backend deployment

## Scope and status

This runbook describes the checked-in production template for an Oracle Cloud Ampere A1 Paid As You Go VM. It does not assert that a VM, DNS record, certificate, database migration, or production deployment currently exists. Record external configuration and real smoke-test results separately.

Production backend releases come only from the generated private backend deployment repository and an explicit canonical `main` SHA. The workflow is manual (`workflow_dispatch`) and builds one immutable `linux/arm64` application image for three separate processes:

```text
Cloudflare proxy
    |
    v
Caddy :443/:80  --->  FastAPI :8000 on private Docker network

Worker             no public port; queue + Connector + dbt execution
Scheduler          no public port; exactly one global enqueue process

Supabase           managed PostgreSQL/Auth/RLS
MotherDuck         managed analytics storage used by Worker/dbt
```

Do not run a local Supabase or MotherDuck service, do not start the Scheduler inside FastAPI, and do not expose API port 8000 on the host.

## Provision the ARM64 host

Use an Ampere A1 Flex shape with an ARM64 operating system image. Size OCPUs, memory, and boot/block storage from measured Worker/dbt load, image retention, Docker logs, and recovery requirements; the repository does not encode a safe universal VM size.

Before the first release:

1. Reserve the public IP so an instance restart does not silently change the origin.
2. Apply operating-system security updates and configure time synchronization.
3. Install Docker Engine and the Docker Compose plugin from an approved, pinned source that supports `linux/arm64`.
4. Install the exact version in the generated release's `supabase-cli.version` only if this host will apply migrations; the migration gate rejects any mismatch.
5. Create a non-interactive deployment account with a restricted SSH key. It may invoke only the fixed root-owned release installer through `sudo`, but that capability is still root-equivalent release authority; protect it accordingly.
6. Authenticate the root Docker client on Oracle to GHCR with a read-only package credential if the image is private. Do not reuse the GitHub Actions package-write token.
7. Configure log rotation and disk monitoring before retaining multiple immutable releases/images.
8. Confirm that every required native Python dependency has an ARM64 wheel or builds successfully in the checked-in multi-stage Dockerfile.

The production workflow itself uses Buildx and QEMU to build only `linux/arm64`, emits provenance and an SBOM, tags the image `sha-FULL_SOURCE_SHA`, refuses to overwrite an existing source-SHA tag, and deploys `GHCR_IMAGE@sha256:DIGEST`. A mutable tag is not the release identity. Python dependencies are fully resolved in `requirements.lock` and installed from a build-stage wheelhouse with `--no-index`. Both Python stages and the ARM64 Caddy image use checked-in digest pins; review and rebuild those pins deliberately rather than silently accepting a moved tag.

```text
python:3.12-slim-bookworm@sha256:8a7e7cc04fd3e2bd787f7f24e22d5d119aa590d429b50c95dfe12b3abe52f48b
caddy:2.11.4-alpine@sha256:1172d4213087d3fc30bafc7ff2c2896180eb0c41ff7f75f315568fb36cabdcba
```

## Network boundaries

### Oracle Security List or NSG

Apply both cloud-network and host-firewall rules. A permissive rule in either layer weakens the boundary.

| Direction | Port/protocol | Source or destination | Purpose |
| --- | --- | --- | --- |
| Inbound | `22/tcp` | Named administration/deployment source addresses only | SSH deployment and emergency access |
| Inbound | `80/tcp` | Cloudflare published ranges and any explicitly required certificate-validation source | HTTP redirect/validation |
| Inbound | `443/tcp` | Cloudflare published ranges when operationally feasible | Public API origin traffic through Cloudflare |
| Inbound | `8000/tcp` | **None** | FastAPI is Docker-internal only |
| Outbound | `443/tcp` | GHCR, Supabase HTTPS/Auth, MotherDuck, connector APIs, package/OS endpoints as approved | Image pulls and application dependencies |
| Outbound | PostgreSQL port from `DATABASE_URL` | Exact Supabase database/pooler destination | Runtime database traffic |
| Outbound | DNS and NTP | Approved resolvers/time sources | Name resolution and clock integrity |

Provider IP ranges change. Review the Cloudflare allowlist as a recurring operation rather than copying a static list into this repository. If port 80 is unnecessary after certificate setup, document and test the decision before closing it; the checked-in Caddy configuration currently publishes both 80 and 443.

Create proxied DNS for `careersignals-api.swiftaihub.com` pointing to the reserved Oracle IP. The proxy must remain enabled for a Cloudflare Origin certificate.

## TLS and reverse proxy

The checked-in Caddyfile expects:

```text
/opt/careersignals/tls/origin.pem
/opt/careersignals/tls/origin.key
```

Use a certificate valid for `careersignals-api.swiftaihub.com`. A Cloudflare Origin certificate is appropriate when all public traffic remains proxied; a publicly trusted certificate may be used under an approved alternative procedure. Configure Cloudflare SSL/TLS as **Full (strict)**. Never use Flexible mode.

Caddy is the only container with host ports. It redirects HTTP to HTTPS, adds basic security headers, trusts the configured proxy chain, and proxies to `api:8000` on the private Compose network. The certificate and key are read-only mounts. Stage rotations as a matched pair, preserve ownership/mode, validate the hostname and expiry, and then recreate only `reverse-proxy`.

## Host directories and ownership

Create persistent control-plane directories outside every Git checkout:

```bash
sudo install -d -m 755 -o root -g root /opt/careersignals
sudo install -d -m 700 -o root -g root /opt/careersignals/env
sudo install -d -m 700 -o root -g root /opt/careersignals/tls
sudo install -d -m 700 -o root -g root /opt/careersignals/backups
sudo install -d -m 700 -o root -g root /opt/careersignals/migration-logs
```

Create empty restricted files before editing through a secure root session:

```bash
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/env/api.env
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/env/worker.env
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/env/scheduler.env
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/tls/origin.pem
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/tls/origin.key
```

Create `migration.env` only when the host is authorized to apply forward migrations:

```bash
sudo install -m 600 -o root -g root /dev/null /opt/careersignals/env/migration.env
```

All env and TLS paths must be regular, non-symlink files owned by `root:root` with mode `600`. The deployment workflow verifies this and never uploads, downloads, overwrites, or prints those files. Compose reads each env file on the host and injects only that service's values; the files are not baked into or copied into the application image.

Use [Environment variables and secret ownership](environment-variables.md) for the complete per-service matrix and placeholder-only outlines. Do not assume that `${OTHER_VARIABLE}` inside an env file will safely construct a connection URL; store each complete secret value through the approved secret-entry procedure.

## Fixed root installer and deployment authority

The workflow never replaces the installed helper or invokes the release bundle's copy as the installer. It uploads `/tmp/release-FULL_SOURCE_SHA.tar.gz`, compares the generated repository's `scripts/install-release.sh` SHA-256 with the installed helper, requires `root:root` mode `755`, and invokes:

```text
/usr/local/sbin/careersignals-install-release
```

For the first release, and whenever a reviewed canonical change modifies `scripts/install-release.sh`, an owner must install the helper manually from the exact generated backend `main` revision:

```bash
sha256sum scripts/install-release.sh
sudo install -m 755 -o root -g root \
  scripts/install-release.sh \
  /usr/local/sbin/careersignals-install-release
sudo sha256sum /usr/local/sbin/careersignals-install-release
sudo stat -c '%U:%G %a' /usr/local/sbin/careersignals-install-release
```

The two hashes must match and metadata must report `root:root 755`. The production workflow stops before deployment on any mismatch; it does not self-update the helper.

Edit a dedicated sudoers fragment with `visudo`:

```bash
sudo visudo -f /etc/sudoers.d/careersignals-deploy
```

Use the actual dedicated account name in the following single-command rule, then ensure the fragment is root-owned mode `440` and validate it with `sudo visudo -cf /etc/sudoers.d/careersignals-deploy`:

```sudoers
REPLACE_WITH_DEPLOYMENT_USER ALL=(root) NOPASSWD: /usr/local/sbin/careersignals-install-release *
```

Do not add the account to the Docker group or grant broad passwordless `sudo`. Nevertheless, do not describe this rule as least privilege: the installer pulls and starts containers and executes reviewed release scripts as root. Anyone who can alter an authorized deployment artifact, canonical-to-deployment sync, workflow, SSH key, or protected GitHub environment can potentially turn that release path into root code execution. Treat the SSH key and all three repository/environment protection boundaries as root-equivalent authority, restrict network access, and require owner review.

## Least-privilege service configuration

The production files have different responsibilities:

- `api.env`: PostgreSQL, Supabase URL/service/JWT configuration, Demo signing, CORS, API quotas/freshness, logging.
- `worker.env`: PostgreSQL, MotherDuck, dbt `prod`, approved Connector sources/credentials, queue polling and writer concurrency.
- `scheduler.env`: PostgreSQL, cron, timezone, trigger mode, logging. No Supabase, MotherDuck, dbt, Demo, or Connector credentials.

The per-user daily submission quota is API-owned. Production requires `USER_PIPELINE_DAILY_LIMIT=4` in `api.env`; do not place it in `worker.env`, where it cannot protect the enqueue endpoint.

The identity represented by `MOTHERDUCK_TOKEN` must own or have shared access to the exact database named by `MOTHERDUCK_DATABASE` (production uses `CareerSignal`). A syntactically valid token is insufficient if that database is unavailable to its identity; the Worker readiness gate intentionally rejects that release instead of accepting a process that cannot execute global or personal refreshes.
- `migration.env`: direct production database URI and project reference. No application runtime secrets beyond what migration requires.

The Dockerfile supplies `/app/dbt` for both dbt directories. Compose supplies separate heartbeat paths in an in-memory `/run/careersignals` filesystem, fixes the MotherDuck writer concurrency to one, fetches up to five independent connector sources in parallel, and uses a 30-minute orphan-recovery window for global refresh records. Do not add host storage for local outputs, spreadsheets, or a DuckDB database; production analytics uses MotherDuck and the serving layer is PostgreSQL.

Validate a staged or current release without displaying values:

```bash
sudo bash /opt/careersignals/current/scripts/verify-environment.sh /opt/careersignals
```

For the first deployment, the workflow runs the same verifier from the staged release before starting containers. Passing verifies file controls, the complete fixed production settings, conditional Connector credentials/identifiers selected by `JOB_SOURCES`, and forbidden cross-service keys. It does not prove credential validity or target identity.

## Backend GitHub production environment

Configure the private backend deployment repository's protected `production` environment.

Secrets:

```text
ORACLE_SSH_PRIVATE_KEY=REPLACE_IN_GITHUB_SECRET_STORE
ORACLE_SSH_KNOWN_HOSTS=REPLACE_WITH_PINNED_HOST_KEY_LINE
```

Variables:

```text
ORACLE_HOST=REPLACE_WITH_RESERVED_HOST_OR_IP
ORACLE_SSH_USER=REPLACE_WITH_DEPLOYMENT_ACCOUNT
ORACLE_DEPLOY_PATH=/opt/careersignals
GHCR_IMAGE=ghcr.io/REPLACE_WITH_OWNER/REPLACE_WITH_IMAGE
```

Require reviewers and keep deployment concurrency at one. `ORACLE_SSH_KNOWN_HOSTS` is integrity-sensitive: obtain and verify the host key out of band. Do not generate trust dynamically during deployment. Business secrets such as `DATABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `MOTHERDUCK_TOKEN`, Demo signing material, and Connector credentials stay only in Oracle service files.

## Manual release workflow

The generated backend repository's workflow runs only from its `main` branch and only after manual dispatch. Before triggering it:

1. Confirm the intended full SHA is reachable from canonical `CareerSignals/main`.
2. Confirm `SOURCE_MANIFEST.json` records that SHA, canonical repository, `main` branch, and backend target.
3. Confirm the previous release directory and immutable image remain available for rollback.
4. Review `pytest -ra` skips; unavailable external RLS tests are unverified, not passing.
5. Confirm the local dbt compile and placeholder-only `prod` parse succeeded.
6. Confirm Oracle env/TLS file ownership, GHCR read access, disk capacity, DNS, firewall, and Full (strict) TLS.
7. If migrations are requested, complete the additional migration gate below.

Workflow inputs:

| Input | Normal release | Meaning |
| --- | --- | --- |
| `expected_source_sha` | Exact 40-character canonical SHA | Must equal the manifest |
| `image_tag` | Empty, or `sha-` plus the exact SHA | Confirmation only; the deployed reference uses the produced digest |
| `apply_migrations` | `false` | Enables the guarded forward-migration script only when intentionally approved |
| `backup_reference` | Empty | Required safe marker name only when migrations are enabled |

There are no partial service inputs. Every successful production release replaces API, Worker, and the singleton Scheduler from one immutable image digest.

The workflow:

1. validates the manifest, split artifact, input syntax, and protected branch;
2. installs dependencies and runs backend tests;
3. resolves dbt packages, compiles the local target, and parses `prod` with a dummy token only;
4. builds and pushes the ARM64 image and records its digest;
5. packages only non-secret release definitions;
6. uses pinned SSH host verification and verifies the exact hash/metadata of the fixed root installer;
7. refuses an existing `/opt/careersignals/releases/FULL_SOURCE_SHA`, so a source SHA cannot be redeployed in place;
8. stages the new release and generates its `release.env`;
9. optionally applies the guarded forward migrations;
10. pulls by digest and atomically deploys API, Worker, and a replacement Scheduler as one application release;
11. advances `/opt/careersignals/current` only after the release health script passes.

If application deployment or health validation fails after service mutation begins, the installer attempts to restore the previously current application release; an initial failed deployment stops the incomplete stack. If that automatic restoration also fails, the workflow reports a critical condition requiring operator intervention. Database migrations are never rolled back automatically. A release directory created by a failed attempt remains immutable and blocks another deployment of the same SHA; diagnose it and generate a new reviewed canonical SHA rather than deleting or overwriting it casually.

The workflow does not configure Oracle, DNS, Cloudflare, Supabase, environment files, TLS files, backups, the fixed installer/sudoers rule, or GHCR pull credentials. `ORACLE_DEPLOY_PATH` must be exactly `/opt/careersignals`; the workflow and scripts reject any alternate path.

## Migration safety gate

Keep `apply_migrations=false` unless all of the following are true:

- the SQL is forward-only and reviewed;
- the current and rollback application revisions are compatible with the resulting schema;
- a production backup or recovery point exists and has been verified sufficiently for the change;
- the exact target project/reference and direct hostname were confirmed out of band;
- a regular `root:root` mode-`600` marker exists at `/opt/careersignals/backups/verified-REPLACE_WITH_REFERENCE`;
- `migration.env` is a regular `root:root` mode-`600` file containing only `SUPABASE_DB_DIRECT_URL` and `SUPABASE_PROJECT_REF`;
- the pinned Supabase CLI is installed and its version has been validated in staging;
- schema, RLS, Auth, Demo, Admin, and two-user checks are ready to run after migration.

The migration script checks the marker, file controls, exact Supabase CLI version, URL scheme, exact `db.PROJECT_REF.supabase.co` hostname, and direct port. It captures a dry run under `/opt/careersignals/migration-logs`, redacts URL-like credentials before displaying the plan, and then applies `supabase db push`. Afterward, the release image checks that all 25 reviewed public tables have RLS enabled and forced, requires the exact 30-name active public-policy inventory, and checks reviewed minimum table, role, command, permissive-mode, and expression invariants.

That schema smoke is a catalog/metadata check, not a behavioral authorization proof. It does not authenticate as two real users, Demo, or Admin and cannot prove that User A is unable to read User B's rows. The live two-user RLS and application isolation suite remains mandatory before declaring production smoke complete.

The Supabase CLI receives `SUPABASE_DB_DIRECT_URL` through `--db-url`, which can expose it in process arguments to sufficiently privileged or same-host observers depending on `/proc` policy. Keep Oracle login access narrow, do not run broad `ps`/process diagnostics during migration, and evaluate an OS-supported `/proc` mount policy such as `hidepid=2` through the host change process. Test Docker and monitoring compatibility before enabling it. Rotate the database credential if process-list exposure is suspected.

Those checks do **not** create or restore a backup, prove that a backup is usable, pause existing writers, or run the full external RLS suite. Therefore the combined workflow migration option is appropriate only for a reviewed backward-compatible migration that is safe while the previous release remains live. If a change needs writer downtime or makes the old application incompatible, do not use the combined release path as-is. Use an approved maintenance plan that quiesces API mutations, Worker, and Scheduler, proves restore in an isolated target, and defines a safe resume point.

Never run `supabase db reset`, delete forward migration files, or pass a database URL through a workflow input. Treat a failed or skipped real integration test as unverified.

## Container and filesystem hardening

The Compose template runs application services as image user/group `10001`, with:

- read-only root filesystems;
- all Linux capabilities dropped;
- `no-new-privileges`;
- writable size-limited `tmpfs` paths only for `/tmp`, heartbeats, DuckDB client state, and dbt logs/target; all remain `noexec` except the narrow `.duckdb` mount, which is `exec,nosuid,nodev` because DuckDB must map the native MotherDuck extension stored there;
- an init process and 45-second stop grace period;
- `restart: unless-stopped`;
- a private bridge network and no Worker/Scheduler ports.

The reverse proxy is also read-only, drops all capabilities except `NET_BIND_SERVICE`, and mounts TLS material read-only. Review every new volume or capability as a security boundary change.

The Worker performs a read-only MotherDuck readiness query before starting its heartbeat. A missing token, blocked extension load, or unavailable analytics database therefore keeps the Worker unhealthy and prevents a release from being marked healthy.

## Health and release verification

On Oracle:

```bash
sudo docker compose \
  --env-file /opt/careersignals/current/release.env \
  -f /opt/careersignals/current/docker-compose.production.yml ps

sudo bash /opt/careersignals/current/scripts/health-check.sh \
  /opt/careersignals/current
```

Externally:

```bash
curl --fail --silent --show-error --max-time 20 \
  https://careersignals-api.swiftaihub.com/api/health
```

The response must be JSON containing `"status":"ok"` and `"source_commit_sha":"FULL_SOURCE_SHA"`. The deployment workflow parses the response and requires the source SHA to equal the manually requested canonical SHA; HTTP 200 alone is insufficient.

The release health script requires:

- API liveness at `/api/health`;
- a fresh Worker heartbeat;
- a fresh Scheduler heartbeat;
- a healthy Caddy admin endpoint;
- exactly one Compose Scheduler container;
- successful public API health through Cloudflare.

A heartbeat proves only that the process heartbeat thread is alive. It does not prove queue progress, Connector credentials, source freshness, MotherDuck publication, dbt correctness, tenant isolation, or a usable database recovery point. The source SHA proves image provenance metadata, not functional correctness. Also inspect queued-run age, recent shared and personal run results, source-level partial failures, the next Scheduler occurrence, PostgreSQL pool health, and safe application logs.

Never print raw container environments or connector exception text while troubleshooting. URLs, headers, and query parameters can contain credentials.

## Exactly one Scheduler

The Scheduler is a singleton, not a horizontally scalable service. The deployment script stops and removes the existing Compose Scheduler before starting its replacement, and the health script fails unless the project has exactly one.

Audit it with:

```bash
sudo docker ps \
  --filter 'label=com.docker.compose.project=careersignals' \
  --filter 'label=com.docker.compose.service=scheduler'
```

Do not run another release directory under a different Compose project name, start `python -m apps.scheduler.main` on the host, or add a GitHub Actions schedule. `CONNECTOR_REFRESH_CRON` belongs only to the continuously running singleton.

## Optional systemd boot integration

The release bundle contains `systemd/careersignals.service`; deployment does not install it. After the first healthy `current` symlink exists, review the unit and then install it through the host's change procedure:

```bash
sudo install -m 644 -o root -g root \
  /opt/careersignals/current/systemd/careersignals.service \
  /etc/systemd/system/careersignals.service
sudo systemctl daemon-reload
sudo systemctl enable --now careersignals.service
```

The unit starts the Compose stack from `current` after Docker and the network. Confirm it does not race with a deployment and that only one operator/systemd path controls the stack.

## Rotation and maintenance

- Rotate an Oracle runtime credential in the one consuming env file, preserve `root:root`/`600`, and recreate only the affected service unless a coordinated cross-service secret such as `DATABASE_URL` changed.
- A database credential shared by API, Worker, and Scheduler requires an atomic maintenance plan across all three files/services.
- Rotate the SSH key in Oracle `authorized_keys` and GitHub together; verify the new key before revoking the old one.
- Rotate the Origin certificate by staging and validating both files, then recreate Caddy.
- Keep old release directories and image digests until their rollback window closes and compatibility is reviewed.
- Patch Docker, the host OS, Caddy, Python base image, and native dependencies through a staged ARM64 release, not an in-place mutation of an application container.

Use [Rollback](rollback.md) for application and data recovery procedures. Do not declare `Oracle deployed` or `Production smoke tested` until the real infrastructure and URLs have been verified.
