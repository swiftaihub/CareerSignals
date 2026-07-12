-- Security helpers, lifecycle hooks, and database invariants that span tables.

create or replace function public.current_app_user_uuid()
returns uuid
language sql
stable
security definer
set search_path = pg_catalog, public
as $function$
    select up.user_uuid
    from public.user_profiles as up
    where up.auth_user_id = auth.uid()
      and up.deleted_at is null
    limit 1
$function$;

create or replace function public.current_app_role()
returns public.user_role
language sql
stable
security definer
set search_path = pg_catalog, public
as $function$
    select up.role
    from public.user_profiles as up
    where up.auth_user_id = auth.uid()
      and up.deleted_at is null
    limit 1
$function$;

create or replace function public.is_current_user_active()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $function$
    select exists (
        select 1
        from public.user_profiles as up
        where up.auth_user_id = auth.uid()
          and up.deleted_at is null
          and up.account_status = 'active'
          and (
              (up.role = 'user' and up.expires_at > now())
              or (up.role in ('admin', 'demo') and up.expires_at is null)
          )
    )
$function$;

create or replace function public.is_current_user_admin()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public
as $function$
    select exists (
        select 1
        from public.user_profiles as up
        where up.auth_user_id = auth.uid()
          and up.deleted_at is null
          and up.role = 'admin'
          and up.account_status = 'active'
    )
$function$;

create or replace function public.remaining_entitlement_days(value timestamptz)
returns integer
language sql
stable
set search_path = pg_catalog, public
as $function$
    select case
        when value is null then 0
        else greatest(
            0,
            ceil(extract(epoch from (value - now())) / 86400.0)::integer
        )
    end
$function$;

create or replace function public.set_row_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
begin
    new.updated_at := now();
    return new;
end
$function$;

create or replace function public.protect_profile_identity()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
begin
    if new.user_uuid <> old.user_uuid
        or new.auth_user_id is distinct from old.auth_user_id
        or new.created_at <> old.created_at then
        raise exception 'Profile tenant identity fields are immutable.'
            using errcode = '23514';
    end if;
    return new;
end
$function$;

-- Auth signup is intentionally conservative: role and account state are never
-- read from user-controlled metadata. Registration remains pending until an
-- administrator activates it. A deterministic fallback username keeps direct
-- provider-created users from violating the non-null profile invariant.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    requested_username text;
    created_user_uuid uuid;
begin
    requested_username := nullif(
        btrim(coalesce(new.raw_user_meta_data ->> 'username', '')),
        ''
    );

    if requested_username is null then
        requested_username := 'user_' || left(replace(new.id::text, '-', ''), 12);
    end if;

    insert into public.user_profiles (
        auth_user_id,
        username,
        email,
        role,
        account_status
    )
    values (
        new.id,
        requested_username,
        new.email,
        'user',
        'pending'
    )
    on conflict (auth_user_id) do update
        set email = excluded.email
    returning user_uuid into created_user_uuid;

    insert into public.user_config_documents (user_uuid, config_type)
    values
        (created_user_uuid, 'candidate_profile'),
        (created_user_uuid, 'jobs_config'),
        (created_user_uuid, 'skill_taxonomy')
    on conflict (user_uuid, config_type) do nothing;

    return new;
end
$function$;

create or replace function public.normalize_application_status()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
declare
    normalized text;
begin
    normalized := lower(replace(replace(btrim(new.application_status), ' ', '_'), '-', '_'));

    if normalized in ('not_applied', 'not_started') then
        normalized := 'not_started';
    end if;

    new.application_status := normalized;
    return new;
end
$function$;

create or replace function public.prepare_config_document_revision()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
begin
    if tg_op = 'UPDATE' then
        if new.config_uuid <> old.config_uuid
            or new.user_uuid <> old.user_uuid
            or new.config_type <> old.config_type then
            raise exception 'Configuration document identity fields are immutable.'
                using errcode = '23514';
        end if;
        new.revision := old.revision + 1;
        new.created_at := old.created_at;
        if new.override_json is distinct from old.override_json
            and new.effective_config_hash is not distinct from old.effective_config_hash then
            new.effective_config_hash := null;
        end if;
    else
        new.revision := greatest(coalesce(new.revision, 1), 1);
    end if;
    return new;
end
$function$;

create or replace function public.record_config_document_version()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    acting_user_uuid uuid;
    source_name text;
begin
    acting_user_uuid := public.current_app_user_uuid();
    if acting_user_uuid is null then
        acting_user_uuid := nullif(
            current_setting('careersignals.changed_by_user_uuid', true),
            ''
        )::uuid;
        source_name := coalesce(
            nullif(current_setting('careersignals.config_change_source', true), ''),
            case when tg_op = 'INSERT' then 'service_insert' else 'service_update' end
        );
    else
        source_name := case
            when public.current_app_role() = 'admin' then 'admin_direct_update'
            when tg_op = 'INSERT' then 'user_direct_insert'
            else 'user_direct_update'
        end;
    end if;

    insert into public.user_config_versions (
        user_uuid,
        config_type,
        revision,
        override_json,
        changed_by_user_uuid,
        change_source
    )
    values (
        new.user_uuid,
        new.config_type,
        new.revision,
        new.override_json,
        acting_user_uuid,
        source_name
    )
    on conflict (user_uuid, config_type, revision) do nothing;

    if tg_op = 'UPDATE' then
        insert into public.user_activity_events (
            user_uuid,
            event_name,
            metadata
        )
        values (
            new.user_uuid,
            'config_updated',
            jsonb_build_object(
                'config_type', new.config_type,
                'revision', new.revision,
                'change_source', source_name
            )
        );
    end if;

    return new;
end
$function$;

create or replace function public.reject_append_only_mutation()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
begin
    raise exception '% is append-only; create a new event/version instead', tg_table_name
        using errcode = '55000';
end
$function$;

-- Defense in depth for the fixed Demo tenant. The API uses the service role,
-- which bypasses RLS, so a trigger guard is required to make Demo read-only.
-- The deterministic seed enables a transaction-local override unavailable to
-- browser clients.
create or replace function public.reject_demo_mutation()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    affected_user_uuid uuid;
    affected_role public.user_role;
    row_document jsonb;
begin
    if coalesce(current_setting('careersignals.allow_demo_seed', true), 'off') = 'on'
        and session_user in ('postgres', 'supabase_admin') then
        if tg_op = 'DELETE' then
            return old;
        end if;
        return new;
    end if;

    row_document := case when tg_op = 'DELETE' then to_jsonb(old) else to_jsonb(new) end;

    if tg_table_name = 'user_profiles' then
        affected_user_uuid := nullif(row_document ->> 'user_uuid', '')::uuid;
        affected_role := nullif(row_document ->> 'role', '')::public.user_role;
    else
        affected_user_uuid := nullif(row_document ->> 'user_uuid', '')::uuid;
        select up.role
        into affected_role
        from public.user_profiles as up
        where up.user_uuid = affected_user_uuid;
    end if;

    if affected_role = 'demo' then
        raise exception 'Demo data is read-only.' using errcode = '42501';
    end if;

    -- Prevent converting an existing Demo profile into another role.
    if tg_table_name = 'user_profiles'
        and tg_op = 'UPDATE'
        and nullif(to_jsonb(old) ->> 'role', '')::public.user_role = 'demo' then
        raise exception 'Demo data is read-only.' using errcode = '42501';
    end if;

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end
$function$;

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
          and upr.is_current_result
    ) then
        raise exception 'Current result rows must reference the user current result run.'
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
    if old.is_current_result and not new.is_current_result and (
        exists (
            select 1 from public.user_job_matches
            where user_uuid = old.user_uuid and run_uuid = old.run_uuid and is_current
        )
        or exists (
            select 1 from public.user_category_summary
            where user_uuid = old.user_uuid and run_uuid = old.run_uuid and is_current
        )
        or exists (
            select 1 from public.user_skill_gap
            where user_uuid = old.user_uuid and run_uuid = old.run_uuid and is_current
        )
        or exists (
            select 1 from public.user_company_priority
            where user_uuid = old.user_uuid and run_uuid = old.run_uuid and is_current
        )
    ) then
        raise exception 'Mark all result rows non-current before unpublishing their run.'
            using errcode = '23514';
    end if;
    return new;
end
$function$;

create or replace function public.require_admin_audit_actor()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
begin
    if not exists (
        select 1
        from public.user_profiles as up
        where up.user_uuid = new.admin_user_uuid
          and up.role = 'admin'
          and up.account_status = 'active'
          and up.deleted_at is null
    ) then
        raise exception 'Admin audit actor must reference an Admin profile.'
            using errcode = '23514';
    end if;
    return new;
end
$function$;

create or replace function public.audit_direct_admin_profile_update()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    actor_uuid uuid;
begin
    if public.is_current_user_admin() then
        actor_uuid := public.current_app_user_uuid();
        insert into public.admin_audit_logs (
            admin_user_uuid,
            target_user_uuid,
            action_name,
            before_state,
            after_state,
            request_id
        )
        values (
            actor_uuid,
            old.user_uuid,
            coalesce(
                nullif(current_setting('careersignals.admin_action_name', true), ''),
                'profile_direct_update'
            ),
            to_jsonb(old),
            to_jsonb(new),
            nullif(current_setting('careersignals.request_id', true), '')
        );
    end if;
    return new;
end
$function$;

drop trigger if exists user_profiles_set_updated_at on public.user_profiles;
create trigger user_profiles_set_updated_at
before update on public.user_profiles
for each row execute function public.set_row_updated_at();

drop trigger if exists user_profiles_protect_identity on public.user_profiles;
create trigger user_profiles_protect_identity
before update on public.user_profiles
for each row execute function public.protect_profile_identity();

drop trigger if exists user_profiles_audit_direct_admin_update on public.user_profiles;
create trigger user_profiles_audit_direct_admin_update
after update on public.user_profiles
for each row execute function public.audit_direct_admin_profile_update();

drop trigger if exists user_config_documents_set_updated_at on public.user_config_documents;
create trigger user_config_documents_set_updated_at
before update on public.user_config_documents
for each row execute function public.set_row_updated_at();

drop trigger if exists user_config_documents_prepare_revision on public.user_config_documents;
create trigger user_config_documents_prepare_revision
before insert or update on public.user_config_documents
for each row execute function public.prepare_config_document_revision();

drop trigger if exists user_config_documents_record_version on public.user_config_documents;
create trigger user_config_documents_record_version
after insert or update on public.user_config_documents
for each row execute function public.record_config_document_version();

drop trigger if exists job_postings_set_updated_at on public.job_postings;
create trigger job_postings_set_updated_at
before update on public.job_postings
for each row execute function public.set_row_updated_at();

drop trigger if exists user_job_statuses_set_updated_at on public.user_job_statuses;
create trigger user_job_statuses_set_updated_at
before update on public.user_job_statuses
for each row execute function public.set_row_updated_at();

drop trigger if exists user_job_statuses_normalize_status on public.user_job_statuses;
create trigger user_job_statuses_normalize_status
before insert or update of application_status on public.user_job_statuses
for each row execute function public.normalize_application_status();

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

drop trigger if exists user_config_versions_append_only on public.user_config_versions;
create trigger user_config_versions_append_only
before update or delete on public.user_config_versions
for each row execute function public.reject_append_only_mutation();

drop trigger if exists user_pipeline_run_events_append_only on public.user_pipeline_run_events;
create trigger user_pipeline_run_events_append_only
before update or delete on public.user_pipeline_run_events
for each row execute function public.reject_append_only_mutation();

drop trigger if exists entitlement_events_append_only on public.entitlement_events;
create trigger entitlement_events_append_only
before update or delete on public.entitlement_events
for each row execute function public.reject_append_only_mutation();

drop trigger if exists admin_audit_logs_append_only on public.admin_audit_logs;
create trigger admin_audit_logs_append_only
before update or delete on public.admin_audit_logs
for each row execute function public.reject_append_only_mutation();

drop trigger if exists admin_audit_logs_require_admin_actor on public.admin_audit_logs;
create trigger admin_audit_logs_require_admin_actor
before insert on public.admin_audit_logs
for each row execute function public.require_admin_audit_actor();

drop trigger if exists user_job_matches_require_current_run on public.user_job_matches;
create trigger user_job_matches_require_current_run
before insert or update of is_current, run_uuid, user_uuid on public.user_job_matches
for each row execute function public.require_current_result_run();

drop trigger if exists user_category_summary_require_current_run on public.user_category_summary;
create trigger user_category_summary_require_current_run
before insert or update of is_current, run_uuid, user_uuid on public.user_category_summary
for each row execute function public.require_current_result_run();

drop trigger if exists user_skill_gap_require_current_run on public.user_skill_gap;
create trigger user_skill_gap_require_current_run
before insert or update of is_current, run_uuid, user_uuid on public.user_skill_gap
for each row execute function public.require_current_result_run();

drop trigger if exists user_company_priority_require_current_run on public.user_company_priority;
create trigger user_company_priority_require_current_run
before insert or update of is_current, run_uuid, user_uuid on public.user_company_priority
for each row execute function public.require_current_result_run();

drop trigger if exists user_pipeline_runs_safe_unpublish on public.user_pipeline_runs;
create trigger user_pipeline_runs_safe_unpublish
before update of is_current_result on public.user_pipeline_runs
for each row execute function public.prevent_unpublishing_referenced_run();

-- Apply the Demo write guard to every relation owned by a user. Shared jobs,
-- connector metadata, and audit evidence are intentionally excluded.
drop trigger if exists user_profiles_reject_demo_mutation on public.user_profiles;
create trigger user_profiles_reject_demo_mutation
before insert or update or delete on public.user_profiles
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_config_documents_reject_demo_mutation on public.user_config_documents;
create trigger user_config_documents_reject_demo_mutation
before insert or update or delete on public.user_config_documents
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_config_versions_reject_demo_mutation on public.user_config_versions;
create trigger user_config_versions_reject_demo_mutation
before insert or update or delete on public.user_config_versions
for each row execute function public.reject_demo_mutation();

drop trigger if exists entitlement_events_reject_demo_mutation on public.entitlement_events;
create trigger entitlement_events_reject_demo_mutation
before insert or update or delete on public.entitlement_events
for each row execute function public.reject_demo_mutation();

drop trigger if exists billing_events_reject_demo_mutation on public.billing_events;
create trigger billing_events_reject_demo_mutation
before insert or update or delete on public.billing_events
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_pipeline_runs_reject_demo_mutation on public.user_pipeline_runs;
create trigger user_pipeline_runs_reject_demo_mutation
before insert or update or delete on public.user_pipeline_runs
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_pipeline_run_events_reject_demo_mutation on public.user_pipeline_run_events;
create trigger user_pipeline_run_events_reject_demo_mutation
before insert or update or delete on public.user_pipeline_run_events
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_job_matches_reject_demo_mutation on public.user_job_matches;
create trigger user_job_matches_reject_demo_mutation
before insert or update or delete on public.user_job_matches
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_job_statuses_reject_demo_mutation on public.user_job_statuses;
create trigger user_job_statuses_reject_demo_mutation
before insert or update or delete on public.user_job_statuses
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_category_summary_reject_demo_mutation on public.user_category_summary;
create trigger user_category_summary_reject_demo_mutation
before insert or update or delete on public.user_category_summary
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_skill_gap_reject_demo_mutation on public.user_skill_gap;
create trigger user_skill_gap_reject_demo_mutation
before insert or update or delete on public.user_skill_gap
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_company_priority_reject_demo_mutation on public.user_company_priority;
create trigger user_company_priority_reject_demo_mutation
before insert or update or delete on public.user_company_priority
for each row execute function public.reject_demo_mutation();

drop trigger if exists user_activity_events_reject_demo_mutation on public.user_activity_events;
create trigger user_activity_events_reject_demo_mutation
before insert or update or delete on public.user_activity_events
for each row execute function public.reject_demo_mutation();

revoke all on function public.current_app_user_uuid() from public;
revoke all on function public.current_app_role() from public;
revoke all on function public.is_current_user_active() from public;
revoke all on function public.is_current_user_admin() from public;
revoke all on function public.remaining_entitlement_days(timestamptz) from public;
revoke all on function public.set_row_updated_at() from public;
revoke all on function public.protect_profile_identity() from public;
revoke all on function public.handle_new_auth_user() from public;
revoke all on function public.normalize_application_status() from public;
revoke all on function public.prepare_config_document_revision() from public;
revoke all on function public.record_config_document_version() from public;
revoke all on function public.reject_append_only_mutation() from public;
revoke all on function public.reject_demo_mutation() from public;
revoke all on function public.require_current_result_run() from public;
revoke all on function public.prevent_unpublishing_referenced_run() from public;
revoke all on function public.require_admin_audit_actor() from public;
revoke all on function public.audit_direct_admin_profile_update() from public;

comment on function public.current_app_user_uuid() is
    'Maps auth.uid() to the stable application tenant UUID without accepting browser-supplied identity.';
comment on function public.is_current_user_active() is
    'True only for active, non-deleted users with a valid entitlement or non-expiring platform role.';
comment on function public.handle_new_auth_user() is
    'Creates a pending application profile and empty configuration overrides after Auth signup.';
