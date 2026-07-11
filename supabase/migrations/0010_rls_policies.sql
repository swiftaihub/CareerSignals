-- Row-level authorization. The backend service role is granted explicit table
-- privileges and is still expected to enforce server-side authorization.

alter table public.user_profiles enable row level security;
alter table public.user_profiles force row level security;
alter table public.user_config_documents enable row level security;
alter table public.user_config_documents force row level security;
alter table public.user_config_versions enable row level security;
alter table public.user_config_versions force row level security;
alter table public.entitlement_events enable row level security;
alter table public.entitlement_events force row level security;
alter table public.billing_events enable row level security;
alter table public.billing_events force row level security;
alter table public.connector_refresh_runs enable row level security;
alter table public.connector_refresh_runs force row level security;
alter table public.connector_source_runs enable row level security;
alter table public.connector_source_runs force row level security;
alter table public.user_pipeline_runs enable row level security;
alter table public.user_pipeline_runs force row level security;
alter table public.user_pipeline_run_events enable row level security;
alter table public.user_pipeline_run_events force row level security;
alter table public.job_postings enable row level security;
alter table public.job_postings force row level security;
alter table public.user_job_matches enable row level security;
alter table public.user_job_matches force row level security;
alter table public.user_job_statuses enable row level security;
alter table public.user_job_statuses force row level security;
alter table public.user_category_summary enable row level security;
alter table public.user_category_summary force row level security;
alter table public.user_skill_gap enable row level security;
alter table public.user_skill_gap force row level security;
alter table public.user_company_priority enable row level security;
alter table public.user_company_priority force row level security;
alter table public.user_activity_events enable row level security;
alter table public.user_activity_events force row level security;
alter table public.admin_audit_logs enable row level security;
alter table public.admin_audit_logs force row level security;

-- Profiles remain readable by their owner even when pending or expired so the
-- application can render the correct account-state page. Deleted users no
-- longer map through current_app_user_uuid().
create policy user_profiles_self_or_admin_select
on public.user_profiles
for select
to authenticated
using (
    user_uuid = public.current_app_user_uuid()
    or public.is_current_user_admin()
);

create policy user_profiles_admin_update
on public.user_profiles
for update
to authenticated
using (public.is_current_user_admin())
with check (public.is_current_user_admin());

create policy user_config_documents_self_or_admin_select
on public.user_config_documents
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_config_documents_self_or_admin_insert
on public.user_config_documents
for insert
to authenticated
with check (
    (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
    )
    or public.is_current_user_admin()
);

create policy user_config_documents_self_or_admin_update
on public.user_config_documents
for update
to authenticated
using (
    (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
    )
    or public.is_current_user_admin()
)
with check (
    (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
    )
    or public.is_current_user_admin()
);

create policy user_config_versions_self_or_admin_select
on public.user_config_versions
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy entitlement_events_self_or_admin_select
on public.entitlement_events
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy billing_events_admin_select
on public.billing_events
for select
to authenticated
using (public.is_current_user_admin());

-- Normal users never query raw connector metadata. The application exposes a
-- separately sanitized freshness response through FastAPI.
create policy connector_refresh_runs_admin_select
on public.connector_refresh_runs
for select
to authenticated
using (public.is_current_user_admin());

create policy connector_source_runs_admin_select
on public.connector_source_runs
for select
to authenticated
using (public.is_current_user_admin());

create policy user_pipeline_runs_self_or_admin_select
on public.user_pipeline_runs
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_pipeline_run_events_self_or_admin_select
on public.user_pipeline_run_events
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

-- Shared jobs are visible only through a current user match. This prevents
-- object-ID guessing from exposing the entire platform job universe.
create policy job_postings_current_match_or_admin_select
on public.job_postings
for select
to authenticated
using (
    public.is_current_user_admin()
    or (
        public.is_current_user_active()
        and exists (
            select 1
            from public.user_job_matches as ujm
            where ujm.job_id = job_postings.job_id
              and ujm.user_uuid = public.current_app_user_uuid()
              and ujm.is_current
        )
    )
);

create policy user_job_matches_self_or_admin_select
on public.user_job_matches
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_job_statuses_self_or_admin_select
on public.user_job_statuses
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_job_statuses_self_or_admin_insert
on public.user_job_statuses
for insert
to authenticated
with check (
    public.is_current_user_admin()
    or (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
        and exists (
            select 1
            from public.user_job_matches as ujm
            where ujm.user_uuid = public.current_app_user_uuid()
              and ujm.job_id = user_job_statuses.job_id
              and ujm.is_current
        )
    )
);

create policy user_job_statuses_self_or_admin_update
on public.user_job_statuses
for update
to authenticated
using (
    public.is_current_user_admin()
    or (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
        and exists (
            select 1
            from public.user_job_matches as ujm
            where ujm.user_uuid = public.current_app_user_uuid()
              and ujm.job_id = user_job_statuses.job_id
              and ujm.is_current
        )
    )
)
with check (
    public.is_current_user_admin()
    or (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
        and exists (
            select 1
            from public.user_job_matches as ujm
            where ujm.user_uuid = public.current_app_user_uuid()
              and ujm.job_id = user_job_statuses.job_id
              and ujm.is_current
        )
    )
);

create policy user_job_statuses_self_or_admin_delete
on public.user_job_statuses
for delete
to authenticated
using (
    public.is_current_user_admin()
    or (
        user_uuid = public.current_app_user_uuid()
        and public.is_current_user_active()
        and public.current_app_role() <> 'demo'
    )
);

create policy user_category_summary_self_or_admin_select
on public.user_category_summary
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_skill_gap_self_or_admin_select
on public.user_skill_gap
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_company_priority_self_or_admin_select
on public.user_company_priority
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy user_activity_events_self_or_admin_select
on public.user_activity_events
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

create policy admin_audit_logs_admin_select
on public.admin_audit_logs
for select
to authenticated
using (public.is_current_user_admin());

-- Anonymous clients receive no direct table privileges. Authenticated grants
-- are intentionally narrow; absent write policies keep service-owned tables
-- immutable from direct client access.
revoke all on table public.user_profiles from anon, authenticated;
revoke all on table public.user_config_documents from anon, authenticated;
revoke all on table public.user_config_versions from anon, authenticated;
revoke all on table public.entitlement_events from anon, authenticated;
revoke all on table public.billing_events from anon, authenticated;
revoke all on table public.connector_refresh_runs from anon, authenticated;
revoke all on table public.connector_source_runs from anon, authenticated;
revoke all on table public.user_pipeline_runs from anon, authenticated;
revoke all on table public.user_pipeline_run_events from anon, authenticated;
revoke all on table public.job_postings from anon, authenticated;
revoke all on table public.user_job_matches from anon, authenticated;
revoke all on table public.user_job_statuses from anon, authenticated;
revoke all on table public.user_category_summary from anon, authenticated;
revoke all on table public.user_skill_gap from anon, authenticated;
revoke all on table public.user_company_priority from anon, authenticated;
revoke all on table public.user_activity_events from anon, authenticated;
revoke all on table public.admin_audit_logs from anon, authenticated;

grant usage on schema public to authenticated, service_role;

grant select on table
    public.user_profiles,
    public.user_config_documents,
    public.user_config_versions,
    public.entitlement_events,
    public.billing_events,
    public.connector_refresh_runs,
    public.connector_source_runs,
    public.user_pipeline_run_events,
    public.job_postings,
    public.user_job_matches,
    public.user_job_statuses,
    public.user_category_summary,
    public.user_skill_gap,
    public.user_company_priority,
    public.user_activity_events,
    public.admin_audit_logs
to authenticated;

grant select (
    run_uuid,
    user_uuid,
    status,
    config_hash,
    config_revision_map,
    submitted_at,
    started_at,
    completed_at,
    published_at,
    jobs_considered,
    jobs_matched,
    error_code,
    public_error_message,
    is_current_result
) on public.user_pipeline_runs to authenticated;

grant update (
    username,
    email,
    role,
    account_status,
    activated_at,
    expires_at,
    last_login_at,
    last_activity_at,
    last_successful_pipeline_run_uuid,
    deleted_at
) on public.user_profiles to authenticated;

grant update (override_json) on public.user_config_documents to authenticated;

grant insert (
    user_uuid,
    job_id,
    application_status,
    notes
) on public.user_job_statuses to authenticated;
grant update (application_status, notes) on public.user_job_statuses to authenticated;
grant delete on table public.user_job_statuses to authenticated;

grant all on table
    public.user_profiles,
    public.user_config_documents,
    public.user_config_versions,
    public.entitlement_events,
    public.billing_events,
    public.connector_refresh_runs,
    public.connector_source_runs,
    public.user_pipeline_runs,
    public.user_pipeline_run_events,
    public.job_postings,
    public.user_job_matches,
    public.user_job_statuses,
    public.user_category_summary,
    public.user_skill_gap,
    public.user_company_priority,
    public.user_activity_events,
    public.admin_audit_logs
to service_role;

grant execute on function public.current_app_user_uuid() to authenticated, service_role;
grant execute on function public.current_app_role() to authenticated, service_role;
grant execute on function public.is_current_user_active() to authenticated, service_role;
grant execute on function public.is_current_user_admin() to authenticated, service_role;
grant execute on function public.remaining_entitlement_days(timestamptz) to authenticated, service_role;
