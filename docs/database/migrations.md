# Database migrations and rollback

CareerSignals uses an ordered, forward-only Supabase migration stack in
`supabase/migrations`. The sixteen files must be applied in numeric order. They
create the PostgreSQL control plane, serving tables, helper functions, RLS,
constraints, and indexes. No migration or seed contains credentials.

## Apply safely

Before applying to a shared environment:

1. Take a Supabase/PostgreSQL backup and record the current migration version.
2. Validate against a disposable local Supabase project first.
3. Apply migrations with the Supabase CLI's local migration workflow.
4. Run the real RLS integration suite with two normal users, one Admin, and an
   anonymous connection.
5. Apply `supabase/seed/0001_demo.sql` only when the fixed Demo tenant is
   desired. Set the backend `DEMO_USER_UUID` to
   `00000000-0000-4000-8000-000000000020`.

The Demo seed creates no Auth user and no password. It inserts a fixed
application profile, one completed result partition, exactly 20 current Demo
matches, and deterministic summary rows. The API must issue its own signed,
short-lived Demo session and map it to that UUID.

The Auth signup trigger creates only a `pending` normal-user profile and three
empty override documents. It never accepts role or account status from Auth
metadata. Activation, entitlement adjustment, suspension, and deletion remain
audited backend service operations.

## Important invariants

- `auth.users.id` maps to a stable `user_profiles.user_uuid`; clients never
  choose their tenant UUID.
- Only one queued/running pipeline and one latest successful result run may
  exist per user.
- Current personal rows must reference a running or completed run for that
  same user. They do not have to reference the latest successful run because
  incremental refreshes preserve unaffected current rows from older runs.
- Publication must merge touched business keys and explicit stale decisions in
  one transaction. It must not clear all current rows for a user just because a
  new run completed.
- Configuration history, entitlement events, pipeline events, and Admin audit
  logs are append-only.
- User-friendly preference saves create one append-only bundle revision and
  associate exactly one version of each generated config document with it. New
  personal runs retain that bundle UUID in addition to their immutable JSON
  snapshot; legacy runs remain valid with a null bundle reference.
- RLS is enabled and forced on every application/control-plane table.
- Demo rows have a service-role-resistant trigger guard. Only the transaction-
  local seed override in the deterministic seed may write them.
- Connector internal error fields are Admin/service-only; user-facing freshness
  responses must be sanitized by FastAPI.

## Rollback

These migrations intentionally do not include destructive down migrations.
For production rollback:

1. Stop API, worker, and scheduler writers.
2. Restore the pre-migration database backup into a new project/database.
3. Point services at the restored database only after smoke and RLS checks.
4. If application code alone must be rolled back, retain the forward-compatible
   schema and deploy the previous application version; do not drop user data.

Never use a recursive schema drop, `supabase db reset`, or ad hoc table deletion
against a shared or production project. Local reset commands are appropriate
only for an explicitly disposable local Supabase instance.
