-- Auditable, non-destructive manual resets for per-user pipeline quotas.
-- Completed run history remains immutable; quota counting ignores completed
-- runs before this marker within the current 6 AM America/New_York window.

alter table public.user_profiles
    add column pipeline_quota_reset_at timestamptz;

create index user_profiles_pipeline_quota_reset_idx
on public.user_profiles(pipeline_quota_reset_at)
where pipeline_quota_reset_at is not null;

comment on column public.user_profiles.pipeline_quota_reset_at is
    'Admin-controlled marker that restores the current personal pipeline allowance without deleting run history.';
