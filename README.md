# CareerSignals

CareerSignals is a hosted, multi-user job-search intelligence application. Supabase Auth and PostgreSQL form the SaaS control plane and serving layer, MotherDuck and dbt perform analytics, FastAPI enforces tenant and account policy, and Next.js serves the public, authenticated, Demo, and Admin experiences.

The central safety rule is that shared job acquisition and personal matching are separate stages with separate ownership:

```text
User-requested personal refresh
Authenticated active user
  -> immutable config snapshot
  -> queued PostgreSQL run
  -> dedicated worker
  -> global shared refresh from all active users' job configs
     -> external Connectors
     -> shared MotherDuck raw/staging
     -> dbt selector: shared_refresh
     -> shared PostgreSQL job_postings
  -> dbt selector: user_refresh
  -> atomic user-only publication
```

Normal users cannot invoke Connectors directly, choose dbt selectors, submit a tenant UUID, or access another tenant's result partition. A personal refresh first runs the system-owned shared refresh, then filters, categorizes, and scores the shared job universe. The fixed Demo tenant has 20 curated jobs and is read-only.

## Repository map

```text
apps/api/                         FastAPI application and authorization boundary
apps/web/                         Next.js App Router frontend and authenticated BFF
apps/worker/                      PostgreSQL queue worker for user dbt runs
apps/scheduler/                   optional cron trigger for shared Connector refresh
config/                           repository defaults and platform Connector config
data/demo/demo_jobs.json          fixed 20-job Demo fixture
dbt/                              shared_refresh and user_refresh models/selectors
docs/                             deployment, operations, and migration guidance
deployment/                       generated-repository deployment overlays
packages/careersignal_core/       repositories, tasks, storage, and publication
scripts/                          bootstrap, seed, migration, and refresh entrypoints
supabase/migrations/              ordered control-plane and RLS migrations
supabase/seed/                    deterministic Demo SQL seed
tests/                            unit, pipeline-isolation, and RLS integration tests
```

## Requirements

- Python 3.11 or 3.12
- Node.js 22 or newer and npm (required by the pinned Cloudflare toolchain)
- Supabase CLI and either a local Supabase stack or a linked Supabase project
- A MotherDuck database and token for shared/user dbt execution
- dbt dependencies installed from `requirements.txt` and `dbt/packages.yml`

Do not use a plain PostgreSQL database as a drop-in replacement for Supabase migrations: the schema references `auth.users`, `auth.uid()`, and Supabase database roles.

## Environment setup

Copy the examples and fill the local files with development credentials:

```powershell
Copy-Item .env.example .env
Copy-Item apps/api/.env.example apps/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
```

The backend environment requires at least:

```dotenv
CAREERSIGNAL_SAAS_MODE=true
CAREERSIGNAL_ENVIRONMENT=development
CAREERSIGNAL_DATA_MODE=postgres
DATABASE_URL=postgresql://...
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_AUDIENCE=authenticated
DEMO_USER_UUID=00000000-0000-4000-8000-000000000020
DEMO_SESSION_SECRET=<long-random-secret>
MOTHERDUCK_TOKEN=...
MOTHERDUCK_DATABASE=CareerSignal
```

The frontend environment is deliberately small:

```dotenv
# Server-only; it is never sent to browser JavaScript.
API_BASE_URL=http://localhost:8000
PASSWORD_RECOVERY_COOKIE_SECRET=

# Supabase project metadata and canonical routing safe for the browser.
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000
NEXT_PUBLIC_BASE_PATH=
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_WITH_BROWSER_KEY
```

Leave `NEXT_PUBLIC_BASE_PATH` empty for ordinary root-path development, or set it to `/careersignals` for a production-equivalent local build. Generate a unique `PASSWORD_RECOVERY_COOKIE_SECRET` of at least 32 bytes for each environment. Password recovery also requires the matching callback URL to be allowed in Supabase; see [Supabase password management configuration](docs/supabase-password-management.md).

Never add `NEXT_PUBLIC_` to `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `MOTHERDUCK_TOKEN`, `DEMO_SESSION_SECRET`, Connector credentials, or any other secret. The browser calls the same-origin Next.js BFF, which attaches the verified server-side session when forwarding allowlisted application requests to FastAPI.

## Supabase and migrations

For an explicitly disposable local environment:

```bash
supabase start
supabase db reset
```

For a hosted development/staging project:

```bash
supabase link --project-ref "$SUPABASE_PROJECT_REF"
supabase db push --dry-run
supabase db push
```

The eighteen files in `supabase/migrations/` must remain in numeric order. Validate them in a disposable project before applying them to a shared environment. Supabase CLI state under `supabase/.temp/` is intentionally ignored; reconstruct a link with `supabase link` rather than committing project metadata.

Bootstrap the first Admin only after migrations have been applied:

```bash
python scripts/bootstrap_admin.py
```

`ADMIN_BOOTSTRAP_PASSWORD` is read from the environment and is never printed. The command is idempotent.

Seed the permanent Demo tenant and its exactly 20 current matches:

```bash
python -m scripts.seed_demo
```

Set `DEMO_USER_UUID=00000000-0000-4000-8000-000000000020`. Demo login uses a short-lived FastAPI-signed token, not an `auth.users` password. The deterministic SQL equivalent is `supabase/seed/0001_demo.sql`.

See [database migrations and rollback](docs/database/migrations.md) before changing a shared database.

## Install

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Frontend dependencies:

```bash
cd apps/web
npm install
cd ../..
```

dbt packages and compile:

```bash
cd dbt
dbt deps
dbt compile --profiles-dir .
cd ..
```

## Run locally

Use four processes from the repository root:

```bash
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
python -m apps.worker.main
python -m apps.scheduler.main
cd apps/web && npm run dev
```

The web application is available at `http://localhost:3000` with an empty base path, or at `http://localhost:3000/careersignals` when `NEXT_PUBLIC_BASE_PATH=/careersignals`. The API health endpoint is `http://localhost:8000/api/health`.

Alternatively, after preparing `.env` and `apps/web/.env.local`:

```bash
docker compose up
```

The Compose stack runs API, worker, scheduler, and web processes. It does not run a fake local MotherDuck server; configure the real MotherDuck service. Supabase remains a local CLI stack or hosted project outside this Compose file.

## Application routes

Routes below are logical application paths. Production serves every one below `/careersignals`; for example, `/dashboard` becomes `https://jobs.swiftaihub.com/careersignals/dashboard`.

Public routes:

- `/` — Home, login/register calls to action, and one-click Demo entry
- `/pricing` — current manual-entitlement pricing placeholder
- `/login` and `/register` — server-action authentication flows
- `/pending` and `/account-expired` — restricted account-state experiences

Authenticated routes:

- `/dashboard`, `/jobs`, `/top-matches`, `/skill-gap`, `/companies`
- `/settings` — account metadata, sanitized source freshness, structured config overrides, revision history, personal run queue/history, and user-scoped export
- `/admin`, `/admin/users`, `/admin/audit` — server-gated Admin experiences

The protected and Admin layouts load `/api/me` server-side. Pending, expired, suspended, and deleted accounts do not render analytical pages. Hiding Admin navigation is only a convenience; FastAPI independently enforces `require_admin` on every Admin API.

Demo instructions are `Username: demo`, `Password: not required`. Demo sessions may read the fixed partition but cannot change statuses/configuration, run a Pipeline, or export the full dataset.

## API surface

Authentication and account:

- `POST /api/auth/login`
- `POST /api/auth/register`
- `POST /api/auth/demo-session`
- `GET /api/me`

User-scoped application data:

- `GET /api/jobs`, `/api/jobs/filter-options`, `/api/jobs/facets`, `/api/jobs/{job_id}`
- `PATCH /api/jobs/{job_id}/status`
- `GET /api/dashboard/summary`, `/api/top-matches`, `/api/category-summary`
- `GET /api/skill-gap`, `/api/company-priority`
- `POST /api/exports/excel`

Configuration and processing:

- `GET /api/configs`, `GET|PUT /api/configs/{config_type}`
- config reset, reset-field, versions, and restore endpoints
- `GET|POST /api/pipeline-runs` plus owned run detail/cancel
- `GET /api/data-freshness` (sanitized and read-only)

Admin:

- `GET /api/admin/metrics`
- paginated `/api/admin/users` lifecycle endpoints
- `GET /api/admin/audit-logs`
- `POST /api/admin/connector-runs` to enqueue an Admin-only global refresh

The former user-facing `/api/pipeline/run`, `/api/dbt/run`, and `/api/dbt/test` operations are deprecated and return `410 Gone`. There is no public Connector refresh endpoint.

## Configuration semantics

`config/candidate_profile.yml`, `config/jobs_config.yml`, and `config/skill_taxonomy.yml` are version-controlled defaults. Each user stores only validated JSON overrides in PostgreSQL:

```text
repository default + user override = effective user configuration
```

Each successful save creates an immutable revision. Restoring an older revision creates another revision; history is not rewritten. `config/platform_connector_config.yml` remains system-owned for Connector sources, budgets, retry, freshness, and optional cron settings. Shared acquisition search categories and broad location filters are built from every active non-Demo user's effective `jobs_config`.

Changing Job Preferences does not query external job APIs in the request/response path. Updated acquisition fields are included in the next scheduled, Admin-triggered, or first-user bootstrap global refresh. The personal worker snapshots the effective configuration and then runs only the fixed `user_refresh` dbt selector for that user/run partition against a successful shared-data version.

## Pipeline operations

The global pipeline is system-owned. It aggregates every eligible active production user's effective `jobs_config`, normalizes and deduplicates connector requests, runs external connectors, refreshes shared dbt models with `shared_refresh`, and publishes shared job data only after the full shared build succeeds. It is scheduled by the runtime environment:

```env
CONNECTOR_REFRESH_CRON=0 7,16,21 * * *
CONNECTOR_REFRESH_TIMEZONE=America/New_York
CONNECTOR_REFRESH_TRIGGER_MODE=scheduled
```

The scheduler enqueues metadata only; the worker claims global runs and uses the same lock/publication path for scheduled, Admin, CLI, and first-user bootstrap refreshes. Normal users do not receive a global refresh endpoint.

The personal pipeline is user-owned. It never imports connector clients, never runs `shared_refresh`, never accepts a browser-supplied `user_uuid`, and never accepts a browser-supplied dbt selector. After a user's bootstrap is complete, `POST /api/pipeline-runs` snapshots that authenticated user's config, binds the run to the latest successfully published shared connector run, and queues only `user_refresh`.

First-user bootstrap is server-orchestrated. The first personal request creates a durable bootstrap workflow, snapshots the user's current config, queues a `first_user_bootstrap` global refresh that includes that frozen acquisition config, waits for successful shared publication, binds the waiting personal run to that exact `connector_run_uuid`, and then runs the personal dbt-only refresh. Duplicate first clicks return the existing workflow instead of creating another global run.

Enqueue a trusted production-equivalent shared refresh manually. This creates a `manual_cli` run and requires the worker to be running; the worker performs connector acquisition, MotherDuck/dbt work, and PostgreSQL publication:

```bash
python scripts/refresh_connectors.py
# Equivalent explicit form:
python scripts/refresh_connectors.py --enqueue
python -m apps.worker.main
```

Run the fixed shared dbt selector directly against already staged shared data:

```bash
cd dbt
dbt build --selector shared_refresh --profiles-dir .
```

Development-only user selector example (use real UUID values and an existing staged snapshot):

```bash
dbt build --selector user_refresh --profiles-dir . \
  --vars '{"user_uuid":"00000000-0000-4000-8000-000000000001","run_uuid":"00000000-0000-4000-8000-000000000002","connector_run_uuid":"00000000-0000-4000-8000-000000000003"}'
```

Never pass an arbitrary selector from a request, run a user refresh with `--full-refresh`, or delete an unqualified multi-user table. A failed user build/publication leaves the previous current result partition unchanged.

## Verification

Backend and database tests:

```bash
python -m pip install -r requirements.txt
pytest
```

Frontend:

```bash
cd apps/web
npm install
npm run test
npm run lint
npm run typecheck
npm run build
```

dbt:

```bash
cd dbt
dbt deps
dbt compile --profiles-dir .
dbt build --selector shared_refresh --profiles-dir .
dbt build --selector user_refresh --profiles-dir . \
  --vars '{"user_uuid":"TEST_UUID","run_uuid":"TEST_RUN_UUID"}'
```


docker:

```bash
docker compose up -d --force-recreate api worker scheduler
```

RLS and two-user tests require real Supabase test credentials from the non-committed `.env`. Skipped integration tests are not equivalent to a pass; inspect the Pytest skip report.

## Production

The generated web repository deploys SSR Next.js to Cloudflare Workers through OpenNext. The generated backend repository deploys one immutable ARM64 image as separate API, worker, and single-scheduler services on Oracle A1 behind Caddy. Keep `USER_PIPELINE_MAX_CONCURRENCY=1` until MotherDuck writer concurrency has been validated, set exact production CORS origins, and store runtime secrets outside Git.

Start with the [production deployment overview](docs/production-deployment.md). The [repository split](docs/repository-splitting.md), [Cloudflare deployment](docs/cloudflare-deployment.md), [Oracle deployment](docs/oracle-deployment.md), [runbook](docs/production-runbook.md), and [rollback guide](docs/rollback.md) contain the release and recovery procedures. The legacy consolidated operational notes remain in [deployment.md](docs/deployment.md).

Billing is currently a manual entitlement placeholder. `estimated_mrr_cents` is a projection for active non-Demo users; only successful billing events count as actual revenue. A future Stripe integration should use verified, idempotent webhooks to append billing and entitlement events rather than mutating remaining-day counters.
