# Domain and `/careersignals` base path

## Trusted URL configuration

Production uses two explicit browser-safe build variables:

```env
NEXT_PUBLIC_SITE_ORIGIN=https://jobs.swiftaihub.com
NEXT_PUBLIC_BASE_PATH=/careersignals
```

The application URL is derived as:

```text
NEXT_PUBLIC_SITE_ORIGIN + NEXT_PUBLIC_BASE_PATH
= https://jobs.swiftaihub.com/careersignals
```

`NEXT_PUBLIC_SITE_URL` is retired because it was ambiguous about whether a path was included. Do not reintroduce parallel canonical URL sources. The site origin must be HTTP(S), contain no credentials/query/fragment/path, and use HTTPS in production. The base path is either empty for ordinary local development or a normalized single path prefix.

## Path helper contract

`apps/web/lib/app-paths.ts` centralizes:

```text
getSiteOrigin()
getBasePath()
getAppUrl()
withBasePath(path)
stripBasePath(path)
buildAuthCallbackUrl(next)
sanitizeInternalRedirect(value, fallback)
getCookiePath()
```

The helper normalizes slashes, preserves query strings/fragments, rejects credentials/control characters/backslash ambiguity and external redirect targets, prevents `/careersignals/careersignals`, and supports an empty local base path.

Use logical paths such as `/dashboard` with Next.js `Link`, router navigation, and framework-managed redirects. Next applies `basePath` to framework routing. Use `withBasePath()` only for APIs that emit raw browser paths, including:

- browser `fetch` and `window.location`;
- same-origin BFF URLs;
- public image source strings;
- manually built callback/absolute URLs;
- cookie paths and non-framework response redirects.

When a browser pathname is fed back into a Server Action, strip the configured base path before passing the logical destination to Next routing. Never prepend `/careersignals` blindly to every link.

## Required routes

All CareerSignals routes are descendants of the base path:

```text
/careersignals
/careersignals/login
/careersignals/register
/careersignals/pricing
/careersignals/pending
/careersignals/account-expired
/careersignals/dashboard
/careersignals/jobs
/careersignals/top-matches
/careersignals/skill-gap
/careersignals/companies
/careersignals/settings
/careersignals/admin
/careersignals/auth/callback
/careersignals/reset-password
/careersignals/api/backend/...
```

The application must not emit `https://jobs.swiftaihub.com/login`, `/dashboard`, or `/api/...` at the host root. It does not require a trailing slash.

## Cloudflare routing

Wrangler defines both:

```text
jobs.swiftaihub.com/careersignals
jobs.swiftaihub.com/careersignals/*
```

This covers pages, base-path `_next` assets, public assets, callback, BFF Route Handlers, Proxy/Middleware behavior, and Server Actions. Do not route `jobs.swiftaihub.com/*` to CareerSignals.

## Supabase Auth configuration

In Supabase Authentication → URL Configuration:

```text
Site URL:
https://jobs.swiftaihub.com/careersignals

Production redirect URL:
https://jobs.swiftaihub.com/careersignals/auth/callback

Local redirect URLs:
http://localhost:3000/auth/callback
http://localhost:3000/careersignals/auth/callback
```

Use exact callbacks; avoid an unnecessary production wildcard. Password-recovery emails use the trusted environment-derived callback, then the signed/validated recovery flow redirects only to `/careersignals/reset-password`. Request `Host` headers and arbitrary `next` URLs are never trusted.

## Cookie scope

Application cookies use:

```text
Path=/careersignals     # production-equivalent base-path build
Path=/                  # empty-base local development
HttpOnly
Secure                  # production
SameSite=Lax
```

Supabase SSR session and isolated recovery cookies must use the same path for set, refresh, and deletion. During migration, explicitly expire legacy root-path custom cookies so root and scoped variants do not coexist. Validate real login, refresh, callback, logout, recovery, and password update after any cookie-option change.

## Metadata and assets

`metadataBase`, canonical/Open Graph URLs, sitemap, robots, and manifest start URL derive from the trusted app URL. `next/image` does not automatically prepend `basePath` to string `src` values, so public image URLs use the path helper. Client bundle scans reject the backend origin and server-secret identifiers.

## Local verification

Ordinary local mode:

```env
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000
NEXT_PUBLIC_BASE_PATH=
```

Production-equivalent local mode:

```env
NEXT_PUBLIC_SITE_ORIGIN=http://localhost:3000
NEXT_PUBLIC_BASE_PATH=/careersignals
```

Verify all required routes, BFF health, callback, public/Next assets, metadata, Server Actions, login refresh/logout, recovery, Demo, and protected redirects. Fail on root-path leaks, duplicate prefixes, redirect loops, mixed content, or missing assets.

