-- Keep cumulative Dashboard totals for the funnel, but maintain separate
-- event-style counts for the daily trend chart.

alter table public.global_job_daily_metrics
    add column new_global_jobs_count integer not null default 0,
    add constraint global_job_daily_metrics_new_count_check check (
        new_global_jobs_count >= 0
    );

alter table public.user_job_daily_metrics
    add column new_user_jobs_count integer not null default 0,
    add column new_applied_jobs_count integer not null default 0,
    add constraint user_job_daily_metrics_new_counts_check check (
        new_user_jobs_count >= 0
        and new_applied_jobs_count >= 0
    );

create index job_postings_first_seen_idx
on public.job_postings(first_seen_at, job_id)
where source_name <> 'demo_seed';

create index user_job_matches_first_created_idx
on public.user_job_matches(user_uuid, job_id, created_at);

create index user_job_status_events_first_application_idx
on public.user_job_status_events(user_uuid, job_id, changed_at)
where new_status in ('applied', 'interview', 'rejected', 'offer');

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
    window_start timestamptz := resolved_metric_date::timestamp
        at time zone 'America/New_York';
    window_end timestamptz := (resolved_metric_date + 1)::timestamp
        at time zone 'America/New_York';
begin
    perform pg_advisory_xact_lock(
        hashtextextended('careersignals:dashboard:global:' || resolved_metric_date::text, 0)
    );
    insert into public.global_job_daily_metrics (
        metric_date,
        global_jobs_count,
        new_global_jobs_count,
        connector_run_uuid,
        recorded_at
    )
    select
        resolved_metric_date,
        count(distinct jobs.job_id) filter (
            where jobs.is_active = true
        )::integer,
        count(distinct jobs.job_id) filter (
            where jobs.first_seen_at >= window_start
              and jobs.first_seen_at < window_end
        )::integer,
        target_connector_run_uuid,
        now()
    from public.job_postings as jobs
    where jobs.source_name <> 'demo_seed'
    on conflict (metric_date) do update set
        global_jobs_count = excluded.global_jobs_count,
        new_global_jobs_count = excluded.new_global_jobs_count,
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
    window_start timestamptz := resolved_metric_date::timestamp
        at time zone 'America/New_York';
    window_end timestamptz := (resolved_metric_date + 1)::timestamp
        at time zone 'America/New_York';
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
        new_user_jobs_count,
        new_applied_jobs_count,
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
        (
            select count(*)::integer
            from (
                select matches.job_id
                from public.user_job_matches as matches
                where matches.user_uuid = target_user_uuid
                group by matches.job_id
                having min(matches.created_at) >= window_start
                   and min(matches.created_at) < window_end
            ) as first_matches
        ),
        (
            select count(*)::integer
            from (
                select events.job_id
                from public.user_job_status_events as events
                where events.user_uuid = target_user_uuid
                  and events.new_status in ('applied', 'interview', 'rejected', 'offer')
                group by events.job_id
                having min(events.changed_at) >= window_start
                   and min(events.changed_at) < window_end
            ) as first_applications
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
        new_user_jobs_count = excluded.new_user_jobs_count,
        new_applied_jobs_count = excluded.new_applied_jobs_count,
        personal_run_uuid = excluded.personal_run_uuid,
        recorded_at = excluded.recorded_at;
end
$function$;

-- Existing snapshot dates can be reconstructed from immutable first-seen,
-- first-match, and application-event timestamps without treating totals as deltas.
update public.global_job_daily_metrics as metrics
set new_global_jobs_count = (
    select count(distinct jobs.job_id)::integer
    from public.job_postings as jobs
    where jobs.source_name <> 'demo_seed'
      and jobs.first_seen_at >= metrics.metric_date::timestamp
          at time zone 'America/New_York'
      and jobs.first_seen_at < (metrics.metric_date + 1)::timestamp
          at time zone 'America/New_York'
);

update public.user_job_daily_metrics as metrics
set new_user_jobs_count = (
        select count(*)::integer
        from (
            select matches.job_id
            from public.user_job_matches as matches
            where matches.user_uuid = metrics.user_uuid
            group by matches.job_id
            having min(matches.created_at) >= metrics.metric_date::timestamp
                       at time zone 'America/New_York'
               and min(matches.created_at) < (metrics.metric_date + 1)::timestamp
                       at time zone 'America/New_York'
        ) as first_matches
    ),
    new_applied_jobs_count = (
        select count(*)::integer
        from (
            select events.job_id
            from public.user_job_status_events as events
            where events.user_uuid = metrics.user_uuid
              and events.new_status in ('applied', 'interview', 'rejected', 'offer')
            group by events.job_id
            having min(events.changed_at) >= metrics.metric_date::timestamp
                       at time zone 'America/New_York'
               and min(events.changed_at) < (metrics.metric_date + 1)::timestamp
                       at time zone 'America/New_York'
        ) as first_applications
    );

comment on column public.global_job_daily_metrics.new_global_jobs_count is
    'Jobs first observed by CareerSignals on this Eastern Time calendar date.';
comment on column public.user_job_daily_metrics.new_user_jobs_count is
    'Jobs first matched to this user on this Eastern Time calendar date.';
comment on column public.user_job_daily_metrics.new_applied_jobs_count is
    'Jobs first reaching an applied-or-later status on this Eastern Time calendar date.';
