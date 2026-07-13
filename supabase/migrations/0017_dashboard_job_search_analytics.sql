-- Daily Dashboard analytics snapshots and immutable application status history.
--
-- Historical snapshots are intentionally backfilled only for the migration day.
-- Existing mutable statuses inform that current snapshot, but no earlier
-- transition events or application journey are synthesized.

create table public.global_job_daily_metrics (
    metric_date date primary key,
    global_jobs_count integer not null,
    connector_run_uuid uuid references public.connector_refresh_runs(connector_run_uuid) on delete set null,
    recorded_at timestamptz not null default now(),
    constraint global_job_daily_metrics_count_check check (global_jobs_count >= 0)
);

create table public.user_job_daily_metrics (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    metric_date date not null,
    user_jobs_count integer not null,
    applied_jobs_count integer not null,
    interview_jobs_count integer not null,
    personal_run_uuid uuid,
    recorded_at timestamptz not null default now(),
    primary key (user_uuid, metric_date),
    constraint user_job_daily_metrics_counts_check check (
        user_jobs_count >= 0
        and applied_jobs_count >= 0
        and interview_jobs_count >= 0
    ),
    constraint user_job_daily_metrics_run_user_fk
        foreign key (personal_run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete set null (personal_run_uuid)
);

create index user_job_daily_metrics_user_date_idx
on public.user_job_daily_metrics(user_uuid, metric_date desc);

create table public.user_job_status_events (
    event_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null,
    job_id text not null,
    previous_status text,
    new_status text not null,
    changed_at timestamptz not null default now(),
    constraint user_job_status_events_user_job_fk
        foreign key (user_uuid, job_id)
        references public.user_job_statuses(user_uuid, job_id)
        on delete restrict,
    constraint user_job_status_events_previous_status_check check (
        previous_status is null
        or previous_status in (
            'not_started', 'saved', 'applied', 'interview',
            'rejected', 'offer', 'archived'
        )
    ),
    constraint user_job_status_events_new_status_check check (
        new_status in (
            'not_started', 'saved', 'applied', 'interview',
            'rejected', 'offer', 'archived'
        )
    )
);

create index user_job_status_events_user_changed_idx
on public.user_job_status_events(user_uuid, changed_at desc);

create index user_job_status_events_user_job_idx
on public.user_job_status_events(user_uuid, job_id, changed_at desc);

create index user_job_status_events_user_new_status_job_idx
on public.user_job_status_events(user_uuid, new_status, job_id);

comment on table public.global_job_daily_metrics is
    'Server-managed daily counts of the active shared global job universe; contains no tenant data.';
comment on table public.user_job_daily_metrics is
    'Tenant-scoped daily Dashboard snapshots. Dates before the first row are unknown, not zero.';
comment on table public.user_job_status_events is
    'Append-only tenant-scoped application status transitions used for ever-reached funnel metrics.';

create or replace function public.upsert_global_job_daily_metric(
    target_connector_run_uuid uuid default null,
    target_metric_date date default null
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    resolved_metric_date date := coalesce(
        target_metric_date,
        (now() at time zone 'America/New_York')::date
    );
begin
    perform pg_advisory_xact_lock(
        hashtextextended('careersignals:dashboard:global:' || resolved_metric_date::text, 0)
    );
    insert into public.global_job_daily_metrics (
        metric_date,
        global_jobs_count,
        connector_run_uuid,
        recorded_at
    )
    select
        resolved_metric_date,
        count(distinct jobs.job_id)::integer,
        target_connector_run_uuid,
        now()
    from public.job_postings as jobs
    where jobs.is_active = true
      and jobs.source_name <> 'demo_seed'
    on conflict (metric_date) do update set
        global_jobs_count = excluded.global_jobs_count,
        connector_run_uuid = excluded.connector_run_uuid,
        recorded_at = excluded.recorded_at;
end
$function$;

create or replace function public.upsert_user_job_daily_metric(
    target_user_uuid uuid,
    target_personal_run_uuid uuid default null,
    target_metric_date date default null
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    resolved_metric_date date := coalesce(
        target_metric_date,
        (now() at time zone 'America/New_York')::date
    );
begin
    perform pg_advisory_xact_lock(
        hashtextextended(
            'careersignals:dashboard:user:'
            || target_user_uuid::text
            || ':'
            || resolved_metric_date::text,
            0
        )
    );
    insert into public.user_job_daily_metrics (
        user_uuid,
        metric_date,
        user_jobs_count,
        applied_jobs_count,
        interview_jobs_count,
        personal_run_uuid,
        recorded_at
    )
    select
        target_user_uuid,
        resolved_metric_date,
        (
            select count(distinct matches.job_id)::integer
            from public.user_job_matches as matches
            where matches.user_uuid = target_user_uuid
              and matches.is_current = true
        ),
        (
            select count(distinct qualified.job_id)::integer
            from (
                select statuses.job_id
                from public.user_job_statuses as statuses
                where statuses.user_uuid = target_user_uuid
                  and statuses.application_status in ('applied', 'interview', 'rejected', 'offer')
                union all
                select events.job_id
                from public.user_job_status_events as events
                where events.user_uuid = target_user_uuid
                  and (
                      events.new_status in ('applied', 'interview', 'rejected', 'offer')
                      or events.previous_status in ('applied', 'interview', 'rejected', 'offer')
                  )
            ) as qualified
        ),
        (
            select count(distinct qualified.job_id)::integer
            from (
                select statuses.job_id
                from public.user_job_statuses as statuses
                where statuses.user_uuid = target_user_uuid
                  and statuses.application_status in ('interview', 'offer')
                union all
                select events.job_id
                from public.user_job_status_events as events
                where events.user_uuid = target_user_uuid
                  and (
                      events.new_status in ('interview', 'offer')
                      or events.previous_status in ('interview', 'offer')
                  )
            ) as qualified
        ),
        coalesce(
            target_personal_run_uuid,
            (
                select existing.personal_run_uuid
                from public.user_job_daily_metrics as existing
                where existing.user_uuid = target_user_uuid
                  and existing.metric_date = resolved_metric_date
            ),
            (
                select runs.run_uuid
                from public.user_pipeline_runs as runs
                where runs.user_uuid = target_user_uuid
                  and runs.is_current_result = true
                limit 1
            )
        ),
        now()
    on conflict (user_uuid, metric_date) do update set
        user_jobs_count = excluded.user_jobs_count,
        applied_jobs_count = excluded.applied_jobs_count,
        interview_jobs_count = excluded.interview_jobs_count,
        personal_run_uuid = excluded.personal_run_uuid,
        recorded_at = excluded.recorded_at;
end
$function$;

create or replace function public.record_user_job_status_event()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    if tg_op = 'INSERT' or new.application_status is distinct from old.application_status then
        insert into public.user_job_status_events (
            user_uuid,
            job_id,
            previous_status,
            new_status,
            changed_at
        ) values (
            new.user_uuid,
            new.job_id,
            case when tg_op = 'UPDATE' then old.application_status else null end,
            new.application_status,
            coalesce(new.updated_at, now())
        );
        perform public.upsert_user_job_daily_metric(new.user_uuid, null, null);
    end if;
    return new;
end
$function$;

drop trigger if exists user_job_statuses_record_event on public.user_job_statuses;
create trigger user_job_statuses_record_event
after insert or update of application_status on public.user_job_statuses
for each row execute function public.record_user_job_status_event();

-- Only the current day is reliable at migration time. Application journey
-- history prior to this feature is deliberately not synthesized.
select public.upsert_global_job_daily_metric(null, null);

select public.upsert_user_job_daily_metric(profiles.user_uuid, null, null)
from public.user_profiles as profiles
where profiles.account_status <> 'deleted';

drop trigger if exists user_job_status_events_append_only on public.user_job_status_events;
create trigger user_job_status_events_append_only
before update or delete on public.user_job_status_events
for each row execute function public.reject_append_only_mutation();

alter table public.global_job_daily_metrics enable row level security;
alter table public.global_job_daily_metrics force row level security;
alter table public.user_job_daily_metrics enable row level security;
alter table public.user_job_daily_metrics force row level security;
alter table public.user_job_status_events enable row level security;
alter table public.user_job_status_events force row level security;

create policy global_job_daily_metrics_active_or_admin_select
on public.global_job_daily_metrics
for select
to authenticated
using (public.is_current_user_active() or public.is_current_user_admin());

create policy user_job_daily_metrics_self_or_admin_select
on public.user_job_daily_metrics
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_job_status_events_self_or_admin_select
on public.user_job_status_events
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

-- Status history is now authoritative. Resetting to not_started remains
-- supported, while deleting the current row would destroy tenant history.
drop policy if exists user_job_statuses_self_or_admin_delete on public.user_job_statuses;
revoke delete on table public.user_job_statuses from authenticated;

revoke all on table public.global_job_daily_metrics from anon, authenticated;
revoke all on table public.user_job_daily_metrics from anon, authenticated;
revoke all on table public.user_job_status_events from anon, authenticated;

grant select on table public.global_job_daily_metrics to authenticated;
grant select on table public.user_job_daily_metrics to authenticated;
grant select on table public.user_job_status_events to authenticated;

grant all on table public.global_job_daily_metrics to service_role;
grant all on table public.user_job_daily_metrics to service_role;
grant all on table public.user_job_status_events to service_role;

revoke all on function public.upsert_global_job_daily_metric(uuid, date) from public;
revoke all on function public.upsert_user_job_daily_metric(uuid, uuid, date) from public;
revoke all on function public.record_user_job_status_event() from public;
grant execute on function public.upsert_global_job_daily_metric(uuid, date) to service_role;
grant execute on function public.upsert_user_job_daily_metric(uuid, uuid, date) to service_role;
grant execute on function public.record_user_job_status_event() to service_role;
