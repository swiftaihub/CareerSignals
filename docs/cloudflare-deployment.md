# Cloudflare Worker deployment

This runbook describes the checked-in deployment contract. It does not assert that a Worker, route, DNS record, secret, or production deployment currently exists; the current handoff status remains not deployed and not production-smoke-tested.

## Adapter and runtime

The production frontend is a full Next.js application, not a static export. It uses SSR, Server Actions, Supabase SSR cookies, Auth callback Route Handlers, a same-origin BFF, and server-only variables.

The deployment package pins:

```text
Node.js 22
Next.js 16.2.x
@opennextjs/cloudflare 1.20.1
Wrangler 4.110.0
```

Next.js 16 Node `proxy.ts` is not currently supported by OpenNext. The application uses the legacy Edge `middleware.ts` path for session refresh and Edge-compatible Web Crypto until adapter support changes. Always prove compatibility with an OpenNext build and workerd preview before upgrading this boundary.

## Worker configuration

`wrangler.jsonc` uses:

- `.open-next/worker.js` as the entry;
- `.open-next/assets` as the static binding;
- `nodejs_compat` and `global_fetch_strictly_public`;
- the Cloudflare Images binding for Next image optimization;
- only the two `/careersignals` routes;
- a current compatibility date.

The production route configuration requires a proxied DNS record on the `swiftaihub.com` zone. It must not claim the entire `jobs.swiftaihub.com` host.

## GitHub production environment

Secret:

```text
CLOUDFLARE_API_TOKEN
```

Variables:

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_WORKER_NAME
NEXT_PUBLIC_SITE_ORIGIN=https://jobs.swiftaihub.com
NEXT_PUBLIC_BASE_PATH=/careersignals
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_REPLACE_WITH_BROWSER_KEY
API_BASE_URL=https://careersignals-api.swiftaihub.com
```

`API_BASE_URL` is non-secret but server-only. It must not use a `NEXT_PUBLIC_` prefix or appear in browser assets. The Supabase publishable key is browser metadata; production requires a current `sb_publishable_` key and rejects legacy JWT, service-role, and secret keys.

Create the Worker object without a production route if necessary, then create `PASSWORD_RECOVERY_COOKIE_SECRET` once as a Cloudflare Worker secret. It is not in Wrangler, GitHub, build variables, or documentation. The workflow verifies that the secret name exists without reading its value. Deploy with `--keep-vars` so dashboard-managed secrets are not removed. Do not generate a new value on each release.

Set `CLOUDFLARE_WORKER_NAME=careersignals-web`. The route validator parses strict JSON and requires that exact name plus exactly `jobs.swiftaihub.com/careersignals` and `jobs.swiftaihub.com/careersignals/*` in the `swiftaihub.com` zone. Comments, substring matches, extra routes, and broader host routes do not pass.

## Manual workflow

The generated repository's `.github/workflows/deploy-production.yml`:

1. runs only on `workflow_dispatch` from deployment `main`;
2. validates the manually confirmed canonical SHA and `SOURCE_MANIFEST.json`;
3. validates the generated artifact and exact routes;
4. installs with `npm ci` on Node 22;
5. runs unit tests, lint, typecheck, and the production Next build;
6. builds OpenNext without hiding a Next build failure;
7. scans `.next/static` and `.open-next/assets` for server configuration;
8. verifies the one-time recovery secret exists, records the previous Cloudflare deployment, deploys with Wrangler while preserving runtime secrets, and records the resulting deployment;
9. verifies the exact Worker name/routes and runs mandatory strict production URL smoke tests;
10. records the canonical SHA and Cloudflare deployment version.

The workflow never runs on push, pull request, or schedule. `CLOUDFLARE_API_TOKEN` is step-scoped only to the secret-inventory check, two deployment-list operations, and deploy operation. Dependency installation, tests, lint, typecheck, Next/OpenNext builds, and bundle scanning do not receive the token.

## Local production-equivalent validation

From a generated web repository with placeholder/test Auth configuration:

```bash
npm ci
npm test
npm run lint
npm run typecheck
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000 \
NEXT_PUBLIC_BASE_PATH=/careersignals \
npm run build
npx opennextjs-cloudflare build
node scripts/scan-client-bundle.mjs .next/static .open-next/assets
npm run preview
```

OpenNext development/build on Windows may require WSL or Linux; GitHub Actions provides the authoritative Linux build. A successful `next build` is not a successful OpenNext build.

## Production checks

Verify:

```text
https://jobs.swiftaihub.com/careersignals
https://jobs.swiftaihub.com/careersignals/login
https://jobs.swiftaihub.com/careersignals/dashboard
https://jobs.swiftaihub.com/careersignals/auth/callback
https://jobs.swiftaihub.com/careersignals/api/backend/api/health
```

The automated smoke is strict and mandatory:

- every public page must return `2xx`;
- every guarded page must return `3xx` with an internal `Location` whose path is exactly `/careersignals/login`;
- a callback without a code must return `3xx` to the internal `/careersignals/forgot-password` path;
- the same-origin BFF health request must return JSON with `status=ok` and the exact canonical source SHA supplied to the web workflow;
- returned public HTML must contain no mixed-content HTTP URL, duplicated base path, or application-root `href`/`src` outside `/careersignals`.

External redirects, guarded `200`, callback `404`, and public `3xx` are failures. These checks still do not exercise a real Supabase session. Manually check assets, canonical metadata, login/refresh/logout, recovery, Demo/Admin/normal-user behavior, and an existing rollback target before declaring production smoke complete.

## Rollback and rotation

Record the previous successful Worker version and source SHA before deployment. Roll back by redeploying the previous generated `main` commit or shifting traffic to a retained known-good Cloudflare version, then rerun the smoke suite.

Rotate the API token in Cloudflare and GitHub if compromised. Rotate the recovery secret only in a maintenance window because it invalidates in-flight recovery intents. Never copy it into GitHub to simplify deployment.
