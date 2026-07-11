# CareerSignals

CareerSignals is a hosted, multi-user job-search intelligence application. Supabase Auth and PostgreSQL form the SaaS control plane and serving layer, MotherDuck and dbt perform analytics, FastAPI enforces tenant and account policy, and Next.js serves the public, authenticated, Demo, and Admin experiences.

The central safety rule is that shared job acquisition and personal matching are separate pipelines:

```text
Scheduled shared refresh                 User-requested personal refresh
Scheduler                                Authenticated active user
  -> external Connectors                   -> immutable config snapshot
  -> shared MotherDuck raw/staging          -> queued PostgreSQL run
  -> dbt selector: shared_refresh            -> dedicated worker
  -> shared PostgreSQL job_postings          -> dbt selector: user_refresh
                                              -> atomic user-only publication
```

Normal users cannot invoke Connectors, choose dbt selectors, submit a tenant UUID, or access another tenant's result partition. A personal refresh only filters, categorizes, and scores the existing shared job universe. The fixed Demo tenant has 20 curated jobs and is read-only.

## Repository map

```text
apps/api/                         FastAPI application and authorization boundary
apps/web/                         Next.js App Router frontend and authenticated BFF
apps/worker/                      PostgreSQL queue worker for user dbt runs
apps/scheduler/                   scheduled shared Connector refresh process
config/                           repository defaults and platform Connector config
data/demo/demo_jobs.json          fixed 20-job Demo fixture
dbt/                              shared_refresh and user_refresh models/selectors
docs/                             deployment, operations, and migration guidance
packages/careersignal_core/       repositories, tasks, storage, and publication
scripts/                          bootstrap, seed, migration, and refresh entrypoints
supabase/migrations/              ordered control-plane and RLS migrations
supabase/seed/                    deterministic Demo SQL seed
tests/                            unit, pipeline-isolation, and RLS integration tests
```

## Requirements

- Python 3.11 or 3.12
- Node.js 20 or newer and npm
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

# Supabase project metadata safe for the browser.
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

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

The eleven files in `supabase/migrations/` must remain in numeric order. Validate them in a disposable project before applying them to a shared environment. Supabase CLI state under `supabase/.temp/` is intentionally ignored; reconstruct a link with `supabase link` rather than committing project metadata.

Bootstrap the first Admin only after migrations have been applied:

```bash
python scripts/bootstrap_admin.py
```

`ADMIN_BOOTSTRAP_PASSWORD` is read from the environment and is never printed. The command is idempotent.

Seed the permanent Demo tenant and its exactly 20 current matches:

```bash
python scripts/seed_demo.py
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

The web application is available at `http://localhost:3000`; the API health endpoint is `http://localhost:8000/api/health`.

Alternatively, after preparing `.env` and `apps/web/.env.local`:

```bash
docker compose up
```

The Compose stack runs API, worker, scheduler, and web processes. It does not run a fake local MotherDuck server; configure the real MotherDuck service. Supabase remains a local CLI stack or hosted project outside this Compose file.

## Application routes

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

The former user-facing `/api/pipeline/run`, `/api/dbt/run`, and `/api/dbt/test` operations are deprecated and return `410 Gone`. There is no public Connector refresh endpoint.

## Configuration semantics

`config/candidate_profile.yml`, `config/jobs_config.yml`, and `config/skill_taxonomy.yml` are version-controlled defaults. Each user stores only validated JSON overrides in PostgreSQL:

```text
repository default + user override = effective user configuration
```

Each successful save creates an immutable revision. Restoring an older revision creates another revision; history is not rewritten. `config/platform_connector_config.yml` is system-owned and cannot be edited from Settings.

Changing Job Preferences does not query external job APIs. Source data is refreshed on the platform schedule; the personal worker snapshots the effective configuration and runs only `user_refresh`.

## Pipeline operations

Run a trusted shared refresh manually:

```bash
python scripts/refresh_connectors.py
```

Run the fixed shared dbt selector directly against already staged shared data:

```bash
cd dbt
dbt build --selector shared_refresh --profiles-dir .
```

Development-only user selector example (use real UUID values and an existing staged snapshot):

```bash
dbt build --selector user_refresh --profiles-dir . \
  --vars '{"user_uuid":"00000000-0000-4000-8000-000000000001","run_uuid":"00000000-0000-4000-8000-000000000002"}'
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

RLS and two-user tests require real Supabase test credentials from the non-committed `.env`. Skipped integration tests are not equivalent to a pass; inspect the Pytest skip report.

## Production

Deploy API, worker, scheduler, and web as separate processes. Run exactly one logical scheduler, keep `USER_PIPELINE_MAX_CONCURRENCY=1` until MotherDuck writer concurrency has been validated, terminate TLS before Next.js, set exact production CORS origins, and store all secrets in the hosting platform's secret manager.

Back up PostgreSQL before migrations, monitor queue age and refresh freshness, and test Demo/user/Admin authorization after every release. Full deployment, health, backup, restore, and rollback procedures are in [production deployment and operations](docs/deployment.md).

Billing is currently a manual entitlement placeholder. `estimated_mrr_cents` is a projection for active non-Demo users; only successful billing events count as actual revenue. A future Stripe integration should use verified, idempotent webhooks to append billing and entitlement events rather than mutating remaining-day counters.
