# CareerSignals web deployment repository

This private repository is generated from `swiftaihub/CareerSignals`. It is a deployment artifact, not a business-development repository. `SOURCE_MANIFEST.json` identifies the canonical branch and full source SHA. Make application changes in the canonical repository and regenerate this repository.

The intended production URL is `https://jobs.swiftaihub.com/careersignals`, served by a Cloudflare Worker built with OpenNext. This repository does not prove that the Worker, route, or DNS has been deployed. The Worker routes intentionally cover only:

```text
jobs.swiftaihub.com/careersignals
jobs.swiftaihub.com/careersignals/*
```

They must never be widened to `jobs.swiftaihub.com/*` without an explicit portfolio-level routing decision.

## Required GitHub production environment

Secret:

```text
CLOUDFLARE_API_TOKEN
```

Variables:

```text
CLOUDFLARE_ACCOUNT_ID
CLOUDFLARE_WORKER_NAME
NEXT_PUBLIC_SITE_ORIGIN
NEXT_PUBLIC_BASE_PATH
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
API_BASE_URL
```

The Cloudflare token should be scoped to this account/Worker and the `swiftaihub.com` zone routes. The workflow injects it only into the Wrangler secret-inventory check, two deployment-list steps, and deploy step; install, tests, lint, typecheck, builds, and bundle scanning never receive it. `CLOUDFLARE_WORKER_NAME` must be exactly `careersignals-web`, and the browser key must be a current `sb_publishable_` key rather than a legacy JWT or server key. `PASSWORD_RECOVERY_COOKIE_SECRET` is a Cloudflare Worker secret, not a GitHub variable. Create the Worker object without a production route if necessary, set this secret once with at least 32 random bytes, and do not rotate it on every deployment:

```bash
npx wrangler secret put PASSWORD_RECOVERY_COOKIE_SECRET --name "$CLOUDFLARE_WORKER_NAME"
```

Set `API_BASE_URL` as the non-secret Worker runtime variable `https://careersignals-api.swiftaihub.com`. Deployments use `--keep-vars` so dashboard-managed secrets remain intact. The checked-in Wrangler configuration declares the `IMAGES` binding used by optimized Next.js images; ensure the account and deployment token permit that binding.

## Manual deployment

1. Confirm the canonical source SHA is on `CareerSignals/main`.
2. Confirm `SOURCE_MANIFEST.json` records that full SHA and `source_branch` is `main`.
3. Open **Actions → Deploy CareerSignals web to production → Run workflow** on this repository's `main` branch.
4. Confirm the one-time recovery secret already exists, then enter the exact canonical SHA. The workflow verifies the secret name without reading its value. Production smoke testing is mandatory and cannot be skipped by a workflow input.
5. Review test, OpenNext build, browser-bundle scan, exact Worker-name/route verification, and smoke-test results.
6. Record the source SHA and Cloudflare deployment version from the job summary.

The workflow is intentionally `workflow_dispatch` only. Pushes, pull requests, and schedules do not deploy. Its strict route parser accepts exactly the two documented routes and rejects comments, extra routes, broader patterns, or a different Worker name.

## Supabase Auth

Configure these exact URLs in Supabase Authentication:

```text
Site URL: https://jobs.swiftaihub.com/careersignals
Redirect URL: https://jobs.swiftaihub.com/careersignals/auth/callback
Local: http://localhost:3000/auth/callback
Local base-path test: http://localhost:3000/careersignals/auth/callback
```

Do not use a broad production wildcard. Test registration, login, refresh, logout, password recovery, password update, pending/expired/suspended states, Demo, and Admin after configuration changes.

## Health and troubleshooting

Run:

```bash
node scripts/smoke-test.mjs
npx wrangler deployments list --name "$CLOUDFLARE_WORKER_NAME"
```

The mandatory smoke requires public pages to return `2xx`, every unauthenticated guarded page to return `3xx` to the internal `/careersignals/login`, a code-less Auth callback to return `3xx` to the internal `/careersignals/forgot-password`, and same-origin BFF health JSON to report `status=ok` plus the exact canonical SHA supplied to the workflow. It also rejects mixed-content URLs, duplicate base paths, and root-level application asset/link leaks. A guarded `200`, external redirect, callback `404`, public `3xx`, or backend SHA mismatch fails. This does not replace real Supabase login, Demo, Admin, normal-user, or two-user testing.

Typical failures:

- Root-path redirects or missing assets: verify the build variables and rebuild; `basePath` is compiled into client bundles.
- BFF 502/503 responses: verify the runtime `API_BASE_URL` and backend certificate/health.
- Recovery 503: verify the Cloudflare recovery secret exists and was not rotated unexpectedly.
- Image failures: verify the Cloudflare Images binding or deliberately configure an alternative loader.
- Routes not invoked: verify both route patterns and that `jobs.swiftaihub.com` is proxied in Cloudflare DNS.

Never print runtime secrets, copy `.env` files into this repository, or bypass the same-origin BFF.

## Rollback and secret rotation

Prefer redeploying the previous known-good generated `main` commit using the manual workflow. If an immediately previous Cloudflare Worker version is retained, use Cloudflare version/deployment controls to move traffic back, then run the smoke test and record the resulting version. Do not claim rollback success until the real URLs pass.

Rotate `PASSWORD_RECOVERY_COOKIE_SECRET` only during an announced maintenance procedure; rotation invalidates in-flight recovery intents. Rotate a compromised Cloudflare API token in GitHub and Cloudflare, then audit workflow logs without copying the token into issues or documentation.
