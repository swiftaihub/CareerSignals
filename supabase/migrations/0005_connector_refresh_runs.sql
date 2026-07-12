-- Platform-owned connector refresh metadata. Internal messages are admin/service only.

create table public.connector_refresh_runs (
    connector_run_uuid uuid primary key default gen_random_uuid(),
    status public.connector_run_status not null default 'queued',
    trigger_type text not null,
    scheduled_for timestamptz,
    started_at timestamptz,
    completed_at timestamptz,
    next_scheduled_at timestamptz,
    shared_dbt_run_completed boolean not null default false,
    jobs_fetched integer not null default 0,
    jobs_retained integer not null default 0,
    jobs_published integer not null default 0,
    error_code text,
    internal_error_message text,
    public_status_message text,
    created_at timestamptz not null default now()
);

create table public.connector_source_runs (
    connector_source_run_uuid uuid primary key default gen_random_uuid(),
    connector_run_uuid uuid not null references public.connector_refresh_runs(connector_run_uuid) on delete cascade,
    source_name text not null,
    status public.connector_run_status not null default 'queued',
    started_at timestamptz,
    completed_at timestamptz,
    records_fetched integer not null default 0,
    records_retained integer not null default 0,
    public_status_message text,
    internal_error_message text,
    unique (connector_run_uuid, source_name)
);

comment on table public.connector_refresh_runs is
    'Global connector/dbt/publication executions; normal users receive only sanitized API projections.';
comment on column public.connector_refresh_runs.internal_error_message is
    'Never expose through a normal-user API or public view.';
comment on column public.connector_source_runs.internal_error_message is
    'Never expose through a normal-user API or public view.';
