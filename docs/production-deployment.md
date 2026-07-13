# Production deployment

## Scope and release gate

`swiftaihub/CareerSignals` is the only development repository. All implementation and validation occurs on `dev`. Do not modify or merge `main` automatically. The owner reviews `dev`, manually merges it to `main`, and then manually generates and deploys an explicit `main` commit SHA.

The two private deployment repositories are generated artifacts:

```text
swiftaihub/careersignals-web-deploy
swiftaihub/careersignals-backend-deploy
```

Do not develop business behavior there. Every generated tree contains `SOURCE_MANIFEST.json` so a deployed Worker/image can be traced to the canonical repository and rolled back.

No production workflow runs on `push`, `pull_request`, or `schedule`. GitHub deployments are manual. The application Scheduler remains a continuously running Oracle process and may use `CONNECTOR_REFRESH_CRON`; that is not a GitHub Actions schedule.

## Production architecture

```text
www.swiftaihub.com                         unchanged portfolio site

jobs.swiftaihub.com/careersignals          Cloudflare Worker / OpenNext / Next.js
  ├─ public and authenticated pages
  ├─ Supabase SSR callback and session refresh
  └─ /api/backend/* same-origin BFF
                 │
                 ▼
careersignals-api.swiftaihub.com            Cloudflare proxy → Oracle A1
  └─ Caddy :443 → FastAPI :8000 (private Docker network)

Oracle A1 (ARM64)
  ├─ API
  ├─ user/global queue Worker
  └─ exactly one global Scheduler

Supabase                                  PostgreSQL, Auth, RLS
MotherDuck + dbt                          shared and per-user analytics
```

The browser calls only the same-origin BFF under `/careersignals`. `API_BASE_URL` is server-only and forwards approved calls to the backend origin. FastAPI remains the authorization boundary, and PostgreSQL RLS, tenant filtering, Demo read-only behavior, Admin checks, account-state enforcement, and fixed dbt selectors must remain intact.

## Canonical URLs

```text
Application: https://jobs.swiftaihub.com/careersignals
Backend:     https://careersignals-api.swiftaihub.com
Auth:        https://jobs.swiftaihub.com/careersignals/auth/callback
Recovery:    https://jobs.swiftaihub.com/careersignals/reset-password
```

CareerSignals does not own `https://jobs.swiftaihub.com/`. The Worker routes cover only `/careersignals` and descendants. See [Domain and base path](domain-and-base-path.md).

## Release sequence

1. On canonical `dev`, run frontend, backend, dbt, split, secret, OpenNext, ARM64, and base-path validation.
2. Review skipped tests separately; an unavailable integration test is not a pass.
3. Review the full diff and possible credential-history findings.
4. The owner manually merges `dev` to canonical `main`.
5. From canonical `main`, approve the canonical GitHub `production` environment and manually run `sync-deployment-repositories.yml` in dry-run mode for the full source SHA. `DEPLOY_REPOSITORIES_TOKEN` is required even in dry run because the workflow clones both private deployment repositories to calculate their real diffs.
6. Review generated file lists, manifests, validation, and independent build results.
7. Rerun the sync with `dry_run=false` to deployment-repository `main` only when the canonical source is reachable from `origin/main`.
8. Prepare or verify Oracle root-owned env/TLS files, the exact-hash root-owned installer at `/usr/local/sbin/careersignals-install-release`, its reviewed sudoers rule, Cloudflare runtime variables/secret, DNS, and Supabase Auth URLs.
9. Manually run the backend production workflow. Keep migrations disabled unless a forward migration and verified recovery point are approved.
10. Verify API, Worker heartbeat/queue behavior, one Scheduler, image digest, and rollback target.
11. Manually run the web production workflow with the same canonical source SHA.
12. Run public, Auth, Demo, Admin, normal-user, two-user isolation, and personal-pipeline smoke tests.
13. Record stable source SHA, Worker version, backend image digest, and previous rollback targets.

Detailed platform instructions are in [Cloudflare deployment](cloudflare-deployment.md) and [Oracle deployment](oracle-deployment.md). Operational steps are in [Production runbook](production-runbook.md).

## Required validation

Canonical source:

```bash
python -m pytest -ra
cd dbt && dbt deps --profiles-dir .
cd dbt && DBT_TARGET=local dbt compile --profiles-dir . --target local
cd apps/web && npm ci
cd apps/web && npm test
cd apps/web && npm run lint
cd apps/web && npm run typecheck
cd apps/web && NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000 NEXT_PUBLIC_BASE_PATH=/careersignals npm run build
```

Generated artifacts must additionally pass:

```text
deterministic split comparison
forbidden-file and secret scan
independent Web install/test/lint/typecheck/build
OpenNext Worker build and client-bundle scan
independent backend pytest/dbt compile
Docker Buildx linux/arm64 build
exact `requirements.lock` install and digest-pinned Python/Caddy base images
Compose configuration and health checks
base-path and production smoke tests
```

Run shared and user dbt builds only against a non-production validation environment unless a production operation is explicitly approved. A user build requires validated `user_uuid`, `run_uuid`, and `connector_run_uuid`; never expose an arbitrary dbt selector to users.

## External configuration checklist

- Cloudflare DNS: proxied records for the frontend host and backend host.
- Cloudflare routes: only the two `/careersignals` patterns.
- Cloudflare SSL/TLS: Full (strict), never Flexible.
- Cloudflare Worker: runtime `API_BASE_URL`; one-time `PASSWORD_RECOVERY_COOKIE_SECRET`; Images binding if optimization is enabled.
- Supabase Auth: exact Site URL and callback allowlist described in the domain guide.
- Oracle: reserved public IP, ARM64 Docker runtime, root-owned env/TLS files, firewall/Security List ports 22/80/443 only.
- Oracle deployment authority: fixed helper at `/usr/local/sbin/careersignals-install-release`, exact hash/metadata check, dedicated sudoers rule, and protections appropriate for root-equivalent release control.
- GitHub production Environments: restricted reviewers, variables, and narrowly scoped secrets.
- GHCR: Oracle has read-only pull access; workflow has package write access.

## Completion status language

Report these independently; never infer one from another:

```text
Implemented
Locally validated
Repository synced
Cloudflare deployed
Oracle deployed
DNS configured
Supabase configured
Production smoke tested
```

Code and templates can be complete while external deployment remains pending credentials, owner review, a manual merge, or console configuration.

Current handoff status:

| Status | Current evidence |
| --- | --- |
| Repository synced | **No** |
| Cloudflare deployed | **No** |
| Oracle deployed | **No** |
| DNS configured | **No** |
| Supabase configured | **No** |
| Production smoke tested | **No** |

Change each status only after retaining evidence from the corresponding owner/manual operation; local validation or checked-in templates do not imply an external deployment.
