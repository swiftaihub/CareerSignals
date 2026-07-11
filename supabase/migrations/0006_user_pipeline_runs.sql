-- PostgreSQL-backed queue and immutable event stream for user dbt refreshes.

create table public.user_pipeline_runs (
    run_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    status public.pipeline_status not null default 'queued',
    config_snapshot jsonb not null,
    config_hash text not null,
    config_revision_map jsonb not null,
    submitted_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    published_at timestamptz,
    jobs_considered integer not null default 0,
    jobs_matched integer not null default 0,
    error_code text,
    public_error_message text,
    internal_error_message text,
    worker_id text,
    is_current_result boolean not null default false,
    constraint user_pipeline_runs_user_run_key unique (user_uuid, run_uuid),
    constraint user_pipeline_runs_run_user_key unique (run_uuid, user_uuid)
);

create table public.user_pipeline_run_events (
    event_uuid uuid primary key default gen_random_uuid(),
    run_uuid uuid not null,
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    event_level text not null,
    event_type text not null,
    message text not null,
    created_at timestamptz not null default now(),
    constraint user_pipeline_run_events_run_user_fk
        foreign key (run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete cascade
);

comment on table public.user_pipeline_runs is
    'Queue rows and immutable config snapshots for user-only dbt processing.';
comment on column public.user_pipeline_runs.internal_error_message is
    'Service/admin diagnostics only; never return through normal-user APIs.';
comment on table public.user_pipeline_run_events is
    'Append-only, user-scoped pipeline progress and diagnostic events.';
