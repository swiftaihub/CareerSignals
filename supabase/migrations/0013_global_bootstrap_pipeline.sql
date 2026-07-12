-- Global acquisition audit, shared-version binding, and durable first-user bootstrap state.

alter table public.connector_refresh_runs
    drop constraint if exists connector_refresh_runs_trigger_type_check;

alter table public.connector_refresh_runs
    add constraint connector_refresh_runs_trigger_type_check check (
        trigger_type in (
            'scheduled',
            'manual_admin',
            'first_user_bootstrap',
            'internal',
            'admin',
            'manual_cli'
        )
    );

alter table public.connector_refresh_runs
    add column if not exists initiating_user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    add column if not exists bootstrap_uuid uuid,
    add column if not exists initiating_user_included boolean not null default false,
    add column if not exists initiating_config_revision_map jsonb,
    add column if not exists initiating_config_hash text,
    add column if not exists initiating_acquisition_hash text,
    add column if not exists resulting_personal_run_uuid uuid,
    add column if not exists included_user_count integer not null default 0,
    add column if not exists acquisition_query_count integer not null default 0;

create table public.connector_run_user_config_snapshots (
    snapshot_uuid uuid primary key default gen_random_uuid(),
    connector_run_uuid uuid not null
        references public.connector_refresh_runs(connector_run_uuid)
        on delete cascade,
    user_uuid uuid not null
        references public.user_profiles(user_uuid)
        on delete cascade,
    config_revisions jsonb not null,
    effective_config_hashes jsonb not null,
    acquisition_config jsonb not null,
    acquisition_hash text not null,
    created_at timestamptz not null default now(),
    unique (connector_run_uuid, user_uuid)
);

create table public.connector_acquisition_queries (
    query_uuid uuid primary key default gen_random_uuid(),
    connector_run_uuid uuid not null
        references public.connector_refresh_runs(connector_run_uuid)
        on delete cascade,
    query_key text not null,
    source_name text not null,
    request_json jsonb not null,
    interested_user_count integer not null,
    status text not null default 'planned',
    records_fetched integer not null default 0,
    internal_error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (connector_run_uuid, query_key)
);

create table public.user_bootstrap_workflows (
    bootstrap_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    status text not null default 'not_started',
    personal_run_uuid uuid references public.user_pipeline_runs(run_uuid) on delete set null,
    connector_run_uuid uuid references public.connector_refresh_runs(connector_run_uuid) on delete set null,
    config_snapshot jsonb,
    config_revision_map jsonb,
    config_hash text,
    acquisition_hash text,
    retry_count integer not null default 0,
    max_retries integer not null default 3,
    public_status_message text,
    internal_error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint user_bootstrap_workflows_status_check check (
        status in (
            'not_started',
            'global_queued',
            'global_running',
            'global_succeeded',
            'personal_queued',
            'personal_running',
            'completed',
            'failed_retryable',
            'personal_failed_retryable',
            'failed_terminal'
        )
    ),
    constraint user_bootstrap_workflows_retry_check check (
        retry_count >= 0 and max_retries >= 0 and retry_count <= max_retries
    ),
    constraint user_bootstrap_workflows_snapshot_object_check check (
        config_snapshot is null or jsonb_typeof(config_snapshot) = 'object'
    )
);

alter table public.user_pipeline_runs
    add column if not exists source_connector_run_uuid uuid references public.connector_refresh_runs(connector_run_uuid),
    add column if not exists is_bootstrap_run boolean not null default false,
    add column if not exists trigger_type text not null default 'user_manual',
    add column if not exists bootstrap_uuid uuid references public.user_bootstrap_workflows(bootstrap_uuid) on delete set null;

insert into public.user_bootstrap_workflows (
    user_uuid,
    status,
    personal_run_uuid,
    config_snapshot,
    config_revision_map,
    config_hash,
    public_status_message,
    completed_at
)
select
    p.user_uuid,
    'completed',
    p.last_successful_pipeline_run_uuid,
    r.config_snapshot,
    r.config_revision_map,
    r.config_hash,
    'Backfilled from an existing successful personal run.',
    coalesce(r.published_at, r.completed_at, now())
from public.user_profiles p
join public.user_pipeline_runs r
  on r.user_uuid = p.user_uuid
 and r.run_uuid = p.last_successful_pipeline_run_uuid
where p.last_successful_pipeline_run_uuid is not null
  and r.status = 'completed'
  and not exists (
      select 1
      from public.user_bootstrap_workflows existing
      where existing.user_uuid = p.user_uuid
        and existing.status = 'completed'
  );

alter table public.connector_refresh_runs
    add constraint connector_refresh_runs_bootstrap_fk
    foreign key (bootstrap_uuid)
    references public.user_bootstrap_workflows(bootstrap_uuid)
    on delete set null
    deferrable initially deferred;

alter table public.connector_refresh_runs
    add constraint connector_refresh_runs_resulting_personal_fk
    foreign key (initiating_user_uuid, resulting_personal_run_uuid)
    references public.user_pipeline_runs(user_uuid, run_uuid)
    on delete set null
    deferrable initially deferred;

alter table public.connector_refresh_runs
    add constraint connector_refresh_runs_audit_counts_check
    check (included_user_count >= 0 and acquisition_query_count >= 0);

alter table public.user_pipeline_runs
    add constraint user_pipeline_runs_trigger_type_check
    check (trigger_type in ('user_manual', 'first_user_bootstrap', 'bootstrap_retry', 'admin_recovery'));

create unique index one_active_bootstrap_workflow_per_user
on public.user_bootstrap_workflows(user_uuid)
where status not in ('completed', 'failed_terminal');

create index connector_refresh_runs_trigger_created_idx
on public.connector_refresh_runs(trigger_type, created_at desc);

create index connector_refresh_runs_bootstrap_idx
on public.connector_refresh_runs(bootstrap_uuid)
where bootstrap_uuid is not null;

create index connector_run_user_snapshots_run_idx
on public.connector_run_user_config_snapshots(connector_run_uuid);

create index connector_run_user_snapshots_user_idx
on public.connector_run_user_config_snapshots(user_uuid, created_at desc);

create index connector_acquisition_queries_run_source_idx
on public.connector_acquisition_queries(connector_run_uuid, source_name);

create index user_bootstrap_workflows_user_status_idx
on public.user_bootstrap_workflows(user_uuid, status);

create index user_bootstrap_workflows_connector_idx
on public.user_bootstrap_workflows(connector_run_uuid)
where connector_run_uuid is not null;

create index user_pipeline_runs_source_connector_idx
on public.user_pipeline_runs(source_connector_run_uuid)
where source_connector_run_uuid is not null;

drop index if exists public.one_active_pipeline_per_user;

create unique index one_active_pipeline_per_user
on public.user_pipeline_runs(user_uuid)
where status in ('queued', 'waiting_for_global', 'running');

alter table public.connector_run_user_config_snapshots enable row level security;
alter table public.connector_run_user_config_snapshots force row level security;
alter table public.connector_acquisition_queries enable row level security;
alter table public.connector_acquisition_queries force row level security;
alter table public.user_bootstrap_workflows enable row level security;
alter table public.user_bootstrap_workflows force row level security;

create policy connector_run_user_snapshots_admin_select
on public.connector_run_user_config_snapshots
for select
to authenticated
using (public.is_current_user_admin());

create policy connector_acquisition_queries_admin_select
on public.connector_acquisition_queries
for select
to authenticated
using (public.is_current_user_admin());

create policy user_bootstrap_workflows_self_or_admin_select
on public.user_bootstrap_workflows
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

revoke all on table
    public.connector_run_user_config_snapshots,
    public.connector_acquisition_queries,
    public.user_bootstrap_workflows
from anon, authenticated;

grant select on table public.user_bootstrap_workflows to authenticated;
grant select on table
    public.connector_run_user_config_snapshots,
    public.connector_acquisition_queries
to authenticated;

grant all on table
    public.connector_run_user_config_snapshots,
    public.connector_acquisition_queries,
    public.user_bootstrap_workflows
to service_role;

comment on table public.connector_run_user_config_snapshots is
    'Run-scoped effective user acquisition snapshots used by the global pipeline.';
comment on table public.connector_acquisition_queries is
    'Run-scoped normalized and deduplicated global acquisition query plan.';
comment on table public.user_bootstrap_workflows is
    'Durable first-user bootstrap orchestration state for personal pipeline requests.';
