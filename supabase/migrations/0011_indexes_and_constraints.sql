-- Cross-table foreign keys, domain checks, and indexes for all tenant-scoped
-- serving, queue, administration, and analytics access paths.

alter table public.user_profiles
    add constraint user_profiles_last_successful_run_fk
    foreign key (user_uuid, last_successful_pipeline_run_uuid)
    references public.user_pipeline_runs(user_uuid, run_uuid)
    deferrable initially deferred;

alter table public.user_profiles
    add constraint user_profiles_username_format_check
    check (username::text ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$'),
    add constraint user_profiles_activation_time_check
    check (activated_at is null or activated_at >= created_at),
    add constraint user_profiles_expiration_time_check
    check (expires_at is null or activated_at is null or expires_at > activated_at),
    add constraint user_profiles_deleted_state_check
    check ((account_status = 'deleted') = (deleted_at is not null)),
    add constraint user_profiles_pending_entitlement_check
    check (
        account_status <> 'pending'
        or (activated_at is null and expires_at is null)
    ),
    add constraint user_profiles_active_user_activation_check
    check (role <> 'user' or account_status <> 'active' or activated_at is not null),
    add constraint user_profiles_active_user_expiration_check
    check (role <> 'user' or account_status <> 'active' or expires_at is not null);

alter table public.user_config_documents
    add constraint user_config_documents_schema_version_check check (schema_version >= 1),
    add constraint user_config_documents_revision_check check (revision >= 1),
    add constraint user_config_documents_override_object_check
        check (jsonb_typeof(override_json) = 'object'),
    add constraint user_config_documents_override_size_check
        check (pg_column_size(override_json) <= 262144);

alter table public.user_config_versions
    add constraint user_config_versions_revision_check check (revision >= 1),
    add constraint user_config_versions_override_object_check
        check (jsonb_typeof(override_json) = 'object'),
    add constraint user_config_versions_override_size_check
        check (pg_column_size(override_json) <= 262144),
    add constraint user_config_versions_source_check check (btrim(change_source) <> '');

alter table public.entitlement_events
    add constraint entitlement_events_type_check check (
        event_type in (
            'initial_activation',
            'admin_grant',
            'admin_reduction',
            'subscription_payment',
            'refund',
            'expiration',
            'manual_override'
        )
    ),
    add constraint entitlement_events_amount_check check (amount_cents >= 0);

alter table public.billing_events
    add constraint billing_events_amount_check check (amount_cents >= 0),
    add constraint billing_events_currency_check check (currency ~ '^[a-z]{3}$'),
    add constraint billing_events_provider_check check (btrim(provider) <> ''),
    add constraint billing_events_type_check check (btrim(event_type) <> ''),
    add constraint billing_events_status_check check (btrim(status) <> ''),
    add constraint billing_events_metadata_object_check
        check (jsonb_typeof(metadata) = 'object');

alter table public.connector_refresh_runs
    add constraint connector_refresh_runs_trigger_type_check check (
        trigger_type in ('scheduled', 'internal', 'admin', 'manual_cli')
    ),
    add constraint connector_refresh_runs_counts_check check (
        jobs_fetched >= 0 and jobs_retained >= 0 and jobs_published >= 0
    ),
    add constraint connector_refresh_runs_time_check check (
        completed_at is null or started_at is null or completed_at >= started_at
    );

alter table public.connector_source_runs
    add constraint connector_source_runs_name_check check (btrim(source_name) <> ''),
    add constraint connector_source_runs_counts_check check (
        records_fetched >= 0 and records_retained >= 0
    ),
    add constraint connector_source_runs_time_check check (
        completed_at is null or started_at is null or completed_at >= started_at
    );

alter table public.user_pipeline_runs
    add constraint user_pipeline_runs_snapshot_object_check
        check (jsonb_typeof(config_snapshot) = 'object'),
    add constraint user_pipeline_runs_snapshot_size_check
        check (pg_column_size(config_snapshot) <= 1048576),
    add constraint user_pipeline_runs_revision_map_object_check
        check (jsonb_typeof(config_revision_map) = 'object'),
    add constraint user_pipeline_runs_hash_check check (btrim(config_hash) <> ''),
    add constraint user_pipeline_runs_counts_check check (
        jobs_considered >= 0 and jobs_matched >= 0 and jobs_matched <= jobs_considered
    ),
    add constraint user_pipeline_runs_start_time_check check (
        started_at is null or started_at >= submitted_at
    ),
    add constraint user_pipeline_runs_completion_time_check check (
        completed_at is null or started_at is null or completed_at >= started_at
    ),
    add constraint user_pipeline_runs_publication_time_check check (
        published_at is null or started_at is null or published_at >= started_at
    );

alter table public.user_pipeline_run_events
    add constraint user_pipeline_run_events_level_check check (
        event_level in ('debug', 'info', 'warning', 'error')
    ),
    add constraint user_pipeline_run_events_type_check check (btrim(event_type) <> ''),
    add constraint user_pipeline_run_events_message_check check (btrim(message) <> '');

alter table public.job_postings
    add constraint job_postings_source_check check (btrim(source_name) <> ''),
    add constraint job_postings_title_check check (btrim(title) <> ''),
    add constraint job_postings_salary_min_check check (salary_min is null or salary_min >= 0),
    add constraint job_postings_salary_max_check check (salary_max is null or salary_max >= 0),
    add constraint job_postings_salary_range_check check (
        salary_min is null or salary_max is null or salary_max >= salary_min
    ),
    add constraint job_postings_seen_time_check check (last_seen_at >= first_seen_at),
    add constraint job_postings_apply_url_check check (
        apply_url is null or apply_url ~* '^https?://'
    );

alter table public.user_job_matches
    add constraint user_job_matches_match_score_check check (match_score between 0 and 100),
    add constraint user_job_matches_title_score_check check (title_score is null or title_score between 0 and 100),
    add constraint user_job_matches_required_skill_score_check check (
        required_skill_score is null or required_skill_score between 0 and 100
    ),
    add constraint user_job_matches_preferred_skill_score_check check (
        preferred_skill_score is null or preferred_skill_score between 0 and 100
    ),
    add constraint user_job_matches_industry_score_check check (
        industry_score is null or industry_score between 0 and 100
    ),
    add constraint user_job_matches_salary_score_check check (
        salary_score is null or salary_score between 0 and 100
    ),
    add constraint user_job_matches_work_arrangement_score_check check (
        work_arrangement_score is null or work_arrangement_score between 0 and 100
    ),
    add constraint user_job_matches_visa_score_check check (
        visa_score is null or visa_score between 0 and 100
    ),
    add constraint user_job_matches_matched_skills_array_check
        check (jsonb_typeof(matched_skills) = 'array'),
    add constraint user_job_matches_missing_skills_array_check
        check (jsonb_typeof(missing_skills) = 'array'),
    add constraint user_job_matches_ranking_reasons_array_check
        check (jsonb_typeof(ranking_reasons) = 'array');

alter table public.user_job_statuses
    add constraint user_job_statuses_value_check check (
        application_status in (
            'saved',
            'applied',
            'interview',
            'rejected',
            'offer',
            'archived',
            'not_started'
        )
    ),
    add constraint user_job_statuses_notes_length_check check (
        notes is null or length(notes) <= 4000
    );

alter table public.user_category_summary
    add constraint user_category_summary_metrics_object_check
        check (jsonb_typeof(metrics) = 'object');

alter table public.user_skill_gap
    add constraint user_skill_gap_metrics_object_check
        check (jsonb_typeof(metrics) = 'object');

alter table public.user_company_priority
    add constraint user_company_priority_metrics_object_check
        check (jsonb_typeof(metrics) = 'object');

alter table public.user_activity_events
    add constraint user_activity_events_name_check check (btrim(event_name) <> ''),
    add constraint user_activity_events_metadata_object_check
        check (jsonb_typeof(metadata) = 'object');

alter table public.admin_audit_logs
    add constraint admin_audit_logs_action_check check (btrim(action_name) <> ''),
    add constraint admin_audit_logs_before_object_check check (
        before_state is null or jsonb_typeof(before_state) = 'object'
    ),
    add constraint admin_audit_logs_after_object_check check (
        after_state is null or jsonb_typeof(after_state) = 'object'
    );

create unique index one_active_pipeline_per_user
on public.user_pipeline_runs(user_uuid)
where status in ('queued', 'running');

create unique index one_current_pipeline_result_per_user
on public.user_pipeline_runs(user_uuid)
where is_current_result;

create unique index user_job_matches_one_current_job
on public.user_job_matches(user_uuid, job_id)
where is_current;

create unique index user_category_summary_one_current_dimension
on public.user_category_summary(user_uuid, category_name)
where is_current;

create unique index user_skill_gap_one_current_dimension
on public.user_skill_gap(user_uuid, canonical_skill)
where is_current;

create unique index user_company_priority_one_current_dimension
on public.user_company_priority(user_uuid, company_name)
where is_current;

create index user_profiles_status_expiration_idx
on public.user_profiles(account_status, expires_at)
where deleted_at is null;

create index user_profiles_created_at_idx
on public.user_profiles(created_at desc);

create index user_profiles_last_activity_idx
on public.user_profiles(last_activity_at desc nulls last)
where deleted_at is null;

create index user_config_documents_user_updated_idx
on public.user_config_documents(user_uuid, updated_at desc);

create index user_config_versions_user_type_created_idx
on public.user_config_versions(user_uuid, config_type, created_at desc);

create index entitlement_events_user_created_idx
on public.entitlement_events(user_uuid, created_at desc);

create index billing_events_user_occurred_idx
on public.billing_events(user_uuid, occurred_at desc);

create index billing_events_status_occurred_idx
on public.billing_events(status, occurred_at desc);

create index connector_refresh_runs_status_created_idx
on public.connector_refresh_runs(status, created_at desc);

create index connector_refresh_runs_completed_idx
on public.connector_refresh_runs(completed_at desc nulls last);

create index connector_source_runs_source_completed_idx
on public.connector_source_runs(source_name, completed_at desc nulls last);

create index user_pipeline_runs_queue_idx
on public.user_pipeline_runs(submitted_at, run_uuid)
where status = 'queued';

create index user_pipeline_runs_user_submitted_idx
on public.user_pipeline_runs(user_uuid, submitted_at desc);

create index user_pipeline_run_events_run_created_idx
on public.user_pipeline_run_events(run_uuid, created_at);

create index job_postings_active_posted_idx
on public.job_postings(is_active, posted_at desc nulls last);

create index job_postings_source_seen_idx
on public.job_postings(source_name, last_seen_at desc);

create index job_postings_company_idx
on public.job_postings(company_name)
where company_name is not null;

create index user_job_matches_current_idx
on public.user_job_matches(user_uuid, is_current, match_score desc);

create index user_job_matches_run_idx
on public.user_job_matches(user_uuid, run_uuid, match_score desc);

create index user_job_matches_job_idx
on public.user_job_matches(job_id, user_uuid);

create index user_job_statuses_user_updated_idx
on public.user_job_statuses(user_uuid, updated_at desc);

create index user_category_summary_current_idx
on public.user_category_summary(user_uuid, is_current, run_uuid);

create index user_skill_gap_current_idx
on public.user_skill_gap(user_uuid, is_current, run_uuid);

create index user_company_priority_current_idx
on public.user_company_priority(user_uuid, is_current, run_uuid);

create index user_activity_events_user_time_idx
on public.user_activity_events(user_uuid, event_time desc);

create index user_activity_events_name_time_idx
on public.user_activity_events(event_name, event_time desc);

create index admin_audit_logs_admin_created_idx
on public.admin_audit_logs(admin_user_uuid, created_at desc);

create index admin_audit_logs_target_created_idx
on public.admin_audit_logs(target_user_uuid, created_at desc)
where target_user_uuid is not null;
