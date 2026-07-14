# Generated deployment repositories

## Source-of-truth policy

`swiftaihub/CareerSignals` is the only development source. Deployment repositories are regenerated from committed Git objects at an explicit full SHA. The split never copies the working directory, so ignored `.env`, local databases, caches, output files, or editor state cannot enter an artifact.

Reusable overlays live in:

```text
deployment/web
deployment/backend
```

`scripts/deployment_split.py` materializes an allowlisted source tree, applies the target overlay, validates it, and generates `SOURCE_MANIFEST.json`.

## Local generation

Use empty output directories:

```bash
python scripts/deployment_split.py build \
  --repo-root . \
  --source-ref FULL_COMMITTED_SHA \
  --target web \
  --output ../generated-web

python scripts/deployment_split.py build \
  --repo-root . \
  --source-ref FULL_COMMITTED_SHA \
  --target backend \
  --output ../generated-backend
```

Validate and summarize without printing configuration values:

```bash
python scripts/deployment_split.py validate --root ../generated-web --target web --expected-source-sha FULL_SHA
python scripts/deployment_split.py validate --root ../generated-backend --target backend --expected-source-sha FULL_SHA
python scripts/deployment_split.py manifest-summary --root ../generated-web
python scripts/deployment_split.py manifest-summary --root ../generated-backend
```

Build each target twice and compare:

```bash
python scripts/deployment_split.py compare --left ../web-a --right ../web-b
python scripts/deployment_split.py compare --left ../backend-a --right ../backend-b
```

Only `generated_at_utc` may differ for the same source SHA.

## Web content

`apps/web` is flattened to the repository root. It is self-contained: `@/*` resolves within the web package and no relative import escapes it. The artifact contains the Next application, public assets, local package/lock/config files, OpenNext/Wrangler configuration, deployment workflow/scripts, README, `.env.example`, and source manifest.

Excluded:

```text
.env and .env.* except .env.example
node_modules
.next
.open-next
.worker-next
coverage
*.tsbuildinfo
keys and credential files
```

## Backend content

The backend preserves repository layout because Python imports, config loading, dbt, fixtures, and operational scripts depend on it. Runtime/validation content includes:

```text
apps/api
apps/worker
apps/scheduler
packages
src
config
dbt
scripts
supabase/config.toml
supabase/migrations
supabase/seed
tests
requirements.txt
requirements.lock
data/demo/demo_jobs.json
data/sample/sample_jobs.json
```

The overlay adds the ARM64 Dockerfile, production Compose, Caddy, health/migration/rollback scripts, the enforced `supabase-cli.version` pin, systemd unit, manual workflow, README, and ignores. `requirements.lock` is the fully resolved production/test dependency set used by both the image build and generated-repository tests; refresh it only in a reviewed Linux Python 3.12 environment.

Excluded:

```text
apps/web
all real env files
data except the two immutable fixtures
outputs and spreadsheets
node_modules and virtual environments
Python/test/dbt caches
local databases
Supabase .temp and .branches state
frontend build output
keys and credential files
```

## Overlay collisions

Unexpected overlay replacement fails. Intentional replacements are listed one path per line in `deployment/<target>/.split-overrides`; that metadata file is not copied. Review every override because it changes generated content.

## Source manifest

Each artifact records:

```json
{
  "source_repository": "swiftaihub/CareerSignals",
  "source_branch": "main",
  "source_commit_sha": "FULL_SHA",
  "generated_at_utc": "ISO_TIMESTAMP",
  "deployment_target": "web-or-backend"
}
```

Production validators require the canonical repository name, full SHA, target, timestamp, and `source_branch=main`.

## Manual sync workflow

`.github/workflows/sync-deployment-repositories.yml` is `workflow_dispatch` only and accepts:

```text
source_ref
target_branch
sync_web
sync_backend
dry_run=true
```

It resolves the source to a full SHA, uses temporary directories/clones, builds and validates artifacts, scans secrets, compares changes, and prints safe manifest summaries. A deployment `main` target is rejected unless the source is reachable from canonical `origin/main` and the dispatched sync tooling itself is running from canonical `main`. It never force-pushes. The job always uses the canonical repository's protected GitHub `production` environment and always requires `DEPLOY_REPOSITORIES_TOKEN`, including `dry_run=true`, because every selected private deployment repository must be cloned to calculate its real staged diff. Dry run creates the local generated commit but does not push it; only `dry_run=false` pushes.

The token should have Contents read/write access only to the two deployment repositories. It is a protected environment secret, never a workflow input. Do not grant organization administration.

## Validation guarantees and limits

The splitter rejects forbidden filenames, escaping symlinks, case-insensitive collisions, missing required files, automatic production triggers, and high-confidence secret patterns without printing matched values. It is a defense layer, not a substitute for GitHub secret scanning and a full-history scanner such as gitleaks. Run both before the first production sync and after any suspected exposure.
