-- Personal serving rows are cumulative current state, not a replacement
-- partition owned by the latest successful run.

alter table public.user_job_matches
    add column if not exists updated_at timestamptz not null default now(),
    add column if not exists first_created_run_uuid uuid,
    add column if not exists last_updated_run_uuid uuid,
    add column if not exists last_evaluated_run_uuid uuid,
    add column if not exists deactivated_at timestamptz,
    add column if not exists deactivation_reason text,
    add column if not exists deactivated_run_uuid uuid;

alter table public.user_category_summary
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now(),
    add column if not exists first_created_run_uuid uuid,
    add column if not exists last_updated_run_uuid uuid,
    add column if not exists last_evaluated_run_uuid uuid,
    add column if not exists deactivated_at timestamptz,
    add column if not exists deactivation_reason text,
    add column if not exists deactivated_run_uuid uuid;

alter table public.user_skill_gap
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now(),
    add column if not exists first_created_run_uuid uuid,
    add column if not exists last_updated_run_uuid uuid,
    add column if not exists last_evaluated_run_uuid uuid,
    add column if not exists deactivated_at timestamptz,
    add column if not exists deactivation_reason text,
    add column if not exists deactivated_run_uuid uuid;

alter table public.user_company_priority
    add column if not exists created_at timestamptz not null default now(),
    add column if not exists updated_at timestamptz not null default now(),
    add column if not exists first_created_run_uuid uuid,
    add column if not exists last_updated_run_uuid uuid,
    add column if not exists last_evaluated_run_uuid uuid,
    add column if not exists deactivated_at timestamptz,
    add column if not exists deactivation_reason text,
    add column if not exists deactivated_run_uuid uuid;

-- The metadata backfill touches deterministic Demo rows; use the same
-- transaction-local service override as the Demo seed.
select set_config('careersignals.allow_demo_seed', 'on', true);

update public.user_job_matches
set first_created_run_uuid = coalesce(first_created_run_uuid, run_uuid),
    last_updated_run_uuid = coalesce(last_updated_run_uuid, run_uuid),
    last_evaluated_run_uuid = coalesce(last_evaluated_run_uuid, run_uuid),
    updated_at = coalesce(updated_at, created_at, now())
where first_created_run_uuid is null
   or last_updated_run_uuid is null
   or last_evaluated_run_uuid is null;

update public.user_category_summary
set first_created_run_uuid = coalesce(first_created_run_uuid, run_uuid),
    last_updated_run_uuid = coalesce(last_updated_run_uuid, run_uuid),
    last_evaluated_run_uuid = coalesce(last_evaluated_run_uuid, run_uuid),
    updated_at = coalesce(updated_at, created_at, now())
where first_created_run_uuid is null
   or last_updated_run_uuid is null
   or last_evaluated_run_uuid is null;

update public.user_skill_gap
set first_created_run_uuid = coalesce(first_created_run_uuid, run_uuid),
    last_updated_run_uuid = coalesce(last_updated_run_uuid, run_uuid),
    last_evaluated_run_uuid = coalesce(last_evaluated_run_uuid, run_uuid),
    updated_at = coalesce(updated_at, created_at, now())
where first_created_run_uuid is null
   or last_updated_run_uuid is null
   or last_evaluated_run_uuid is null;

update public.user_company_priority
set first_created_run_uuid = coalesce(first_created_run_uuid, run_uuid),
    last_updated_run_uuid = coalesce(last_updated_run_uuid, run_uuid),
    last_evaluated_run_uuid = coalesce(last_evaluated_run_uuid, run_uuid),
    updated_at = coalesce(updated_at, created_at, now())
where first_created_run_uuid is null
   or last_updated_run_uuid is null
   or last_evaluated_run_uuid is null;

create index if not exists user_job_matches_deactivation_idx
on public.user_job_matches(user_uuid, deactivated_run_uuid, deactivation_reason)
where is_current = false;

create or replace function public.require_current_result_run()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    if new.is_current and not exists (
        select 1
        from public.user_pipeline_runs as upr
        where upr.run_uuid = new.run_uuid
          and upr.user_uuid = new.user_uuid
          and upr.status in ('running', 'completed')
    ) then
        raise exception 'Current result rows must reference a running or completed run for the same user.'
            using errcode = '23514';
    end if;
    return new;
end
$function$;

create or replace function public.prevent_unpublishing_referenced_run()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    -- Current personal rows may keep lineage to older completed runs after a
    -- newer incremental refresh becomes the user's watermark.
    return new;
end
$function$;

comment on table public.user_job_matches is
    'Cumulative user-specific match current state plus historical inactive versions. Current visibility is keyed by user_uuid and job_id; run_uuid is lineage.';

comment on column public.user_job_matches.first_created_run_uuid is
    'First personal pipeline run that created this user/job business record.';
comment on column public.user_job_matches.last_updated_run_uuid is
    'Most recent personal pipeline run that wrote this row version.';
comment on column public.user_job_matches.last_evaluated_run_uuid is
    'Most recent personal pipeline run that evaluated this user/job record.';
comment on column public.user_job_matches.deactivation_reason is
    'Explicit reason an older row version or stale record was made non-current.';
comment on function public.require_current_result_run() is
    'Validates current personal rows reference the same user and a running or completed run; it does not require the latest-result run.';
