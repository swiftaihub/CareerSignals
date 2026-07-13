# Supabase password management configuration

CareerSignals uses Supabase Auth for password recovery and authenticated password changes. The application code does not store passwords or password hashes. Complete the hosted-project configuration below before enabling these flows in production.

## Application environment

Set the following values in the Next.js deployment environment (not in committed `.env` files):

```dotenv
NEXT_PUBLIC_SITE_ORIGIN=https://jobs.swiftaihub.com
NEXT_PUBLIC_BASE_PATH=/careersignals
PASSWORD_RECOVERY_COOKIE_SECRET=<unique random value of at least 32 bytes>
```

The trusted production application URL is derived as `NEXT_PUBLIC_SITE_ORIGIN + NEXT_PUBLIC_BASE_PATH`, yielding `https://jobs.swiftaihub.com/careersignals`. The origin must use HTTPS in production and must not contain a path. `PASSWORD_RECOVERY_COOKIE_SECRET` is server-only and signs the short-lived recovery-intent cookie; store it once as a Cloudflare Worker Secret and never expose it to browser code.

The existing `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` remain the only Supabase values used by the web application. Never add a service-role key, Supabase Management API token, SMTP password, or production secret to the repository.

## Auth URL Configuration

In the Supabase Dashboard, open **Authentication → URL Configuration**.

1. Set **Site URL** to `https://jobs.swiftaihub.com/careersignals`.
2. Add every supported callback to **Redirect URLs** using exact URLs where possible:

   - Local development: `http://localhost:3000/auth/callback`
   - Production-equivalent local development: `http://localhost:3000/careersignals/auth/callback`
   - Production: `https://jobs.swiftaihub.com/careersignals/auth/callback`
   - Add explicit staging/preview callbacks only for environments that are intentionally supported.

The application calls `resetPasswordForEmail` with a trusted callback ending in `/careersignals/auth/callback?next=/reset-password` in production. It does not construct production email links from a request `Host` header. The callback validates `next` as an internal logical path and resolves recovery only to `/careersignals/reset-password`; external hosts and duplicate/missing base paths are rejected. Supabase must allow the callback URL or it will fall back to the configured Site URL.

## Require the current password

In **Authentication → Providers → Email** (the exact Dashboard grouping can change), enable **Require current password when changing password**. This server-side setting is required for the Settings form’s `current_password` field to be enforced.

CareerSignals locks `@supabase/supabase-js` to a release newer than 2.102.0, where `current_password` is supported. Managed Supabase Auth must also be current enough to support the setting. For self-hosted Auth, enable the equivalent `GOTRUE_SECURITY_UPDATE_PASSWORD_REQUIRE_CURRENT_PASSWORD` setting and verify the deployed Auth version before release.

Consider enabling the **Password changed** security notification as an additional account-safety signal.

## Password Recovery email template

Open **Authentication → Email Templates → Reset Password**.

Recommended subject:

```text
Reset your CareerSignals password
```

Recommended HTML body:

```html
<h2>Reset your CareerSignals password</h2>

<p>
  We received a request to reset the password for your CareerSignals account.
</p>

<p>
  <a href="{{ .ConfirmationURL }}">Reset password</a>
</p>

<p>
  This link will expire for security reasons.
  If you did not request a password reset, you can safely ignore this email.
</p>

<p>
  CareerSignals<br />
  Turn job-market data into prioritized career opportunities.
</p>
```

Preserve `{{ .ConfirmationURL }}` exactly. It contains the Supabase-generated one-time confirmation link and the allowed application redirect. Disable link tracking in the email provider because rewritten links can interfere with authentication links.

Editing this template changes the subject and body. It does not fully brand the sender identity.

## Custom SMTP

Configure **Authentication → SMTP Settings** for production delivery:

- Sender name: `CareerSignals`
- From address: a verified mailbox on a CareerSignals-controlled domain
- Reply-to address: a monitored support mailbox
- Domain authentication: SPF, DKIM, and DMARC enabled and verified

Store SMTP credentials only in Supabase’s protected Dashboard configuration or an approved secret manager. Supabase’s default email service is intended for trying the product and must not be treated as the production delivery solution; it has restrictive limits and no fully branded sender.

## Release checks

Before production rollout:

1. Request a reset for both a registered and an unregistered syntactically valid email and verify the UI response is identical.
2. Open a current recovery email in the same browser that requested it and confirm it reaches `/careersignals/reset-password` in the production-equivalent build.
3. Confirm expired and reused links return to the friendly request-new-link state.
4. While a recovery session is active, try the Dashboard, Settings, and application API routes; each must be blocked or redirected to the base-path-aware reset-password route.
5. Reset a disposable account, then verify the old password fails, the new password succeeds, and existing refresh-token sessions are revoked.
6. In Settings, verify an incorrect current password fails and a correct current password changes the password, signs the user out, and requires the new password at the next login.
7. Verify the demo account shows the disabled password-change control.

The existing FastAPI administrator password-reset operation initiates email outside the recipient’s browser and therefore does not share this browser-bound PKCE verifier. Treat administrator-initiated recovery as a separate future token-hash workflow; direct users to the self-service **Forgot password?** flow for this implementation.
