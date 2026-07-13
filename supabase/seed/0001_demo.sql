-- Deterministic, idempotent read-only Demo tenant seed.
-- This file deliberately creates no auth.users row and contains no password.
-- Configure DEMO_USER_UUID in backend environments to the UUID below.

begin;

select set_config('careersignals.allow_demo_seed', 'on', true);
select set_config('careersignals.config_change_source', 'demo_seed', true);
select set_config(
    'careersignals.changed_by_user_uuid',
    '00000000-0000-4000-8000-000000000020',
    true
);

insert into public.user_profiles (
    user_uuid,
    auth_user_id,
    username,
    email,
    role,
    account_status,
    created_at,
    activated_at,
    expires_at,
    deleted_at
)
values (
    '00000000-0000-4000-8000-000000000020',
    null,
    'demo',
    null,
    'demo',
    'active',
    '2026-01-01 00:00:00+00',
    '2026-01-01 00:00:00+00',
    null,
    null
)
on conflict (user_uuid) do update
set username = excluded.username,
    email = excluded.email,
    role = excluded.role,
    account_status = excluded.account_status,
    activated_at = excluded.activated_at,
    expires_at = excluded.expires_at,
    deleted_at = excluded.deleted_at;

insert into public.user_config_documents (
    user_uuid,
    config_type,
    override_json,
    schema_version,
    revision,
    effective_config_hash
)
values
    ('00000000-0000-4000-8000-000000000020', 'candidate_profile', '{}'::jsonb, 1, 1, 'demo-repository-default'),
    ('00000000-0000-4000-8000-000000000020', 'jobs_config', '{}'::jsonb, 1, 1, 'demo-repository-default'),
    ('00000000-0000-4000-8000-000000000020', 'skill_taxonomy', '{}'::jsonb, 1, 1, 'demo-repository-default')
on conflict (user_uuid, config_type) do nothing;

insert into public.user_config_versions (
    version_uuid,
    user_uuid,
    config_type,
    revision,
    override_json,
    changed_by_user_uuid,
    change_source,
    created_at
)
values
    ('00000000-0000-4000-8000-000000000030', '00000000-0000-4000-8000-000000000020', 'candidate_profile', 1, '{}'::jsonb, '00000000-0000-4000-8000-000000000020', 'demo_seed', '2026-01-01 00:00:00+00'),
    ('00000000-0000-4000-8000-000000000031', '00000000-0000-4000-8000-000000000020', 'jobs_config', 1, '{}'::jsonb, '00000000-0000-4000-8000-000000000020', 'demo_seed', '2026-01-01 00:00:00+00'),
    ('00000000-0000-4000-8000-000000000032', '00000000-0000-4000-8000-000000000020', 'skill_taxonomy', 1, '{}'::jsonb, '00000000-0000-4000-8000-000000000020', 'demo_seed', '2026-01-01 00:00:00+00')
on conflict (user_uuid, config_type, revision) do nothing;

-- Retire any prior Demo partition before switching the deterministic partition.
update public.user_job_matches
set is_current = false
where user_uuid = '00000000-0000-4000-8000-000000000020'
  and is_current;

update public.user_category_summary
set is_current = false
where user_uuid = '00000000-0000-4000-8000-000000000020'
  and is_current;

update public.user_skill_gap
set is_current = false
where user_uuid = '00000000-0000-4000-8000-000000000020'
  and is_current;

update public.user_company_priority
set is_current = false
where user_uuid = '00000000-0000-4000-8000-000000000020'
  and is_current;

update public.user_pipeline_runs
set is_current_result = false
where user_uuid = '00000000-0000-4000-8000-000000000020'
  and run_uuid <> '00000000-0000-4000-8000-000000000021'
  and is_current_result;

insert into public.user_pipeline_runs (
    run_uuid,
    user_uuid,
    status,
    config_snapshot,
    config_hash,
    config_revision_map,
    submitted_at,
    started_at,
    completed_at,
    published_at,
    jobs_considered,
    jobs_matched,
    worker_id,
    is_current_result
)
values (
    '00000000-0000-4000-8000-000000000021',
    '00000000-0000-4000-8000-000000000020',
    'completed',
    '{"candidate_profile":{},"jobs_config":{},"skill_taxonomy":{}}'::jsonb,
    'demo-repository-default',
    '{"candidate_profile":1,"jobs_config":1,"skill_taxonomy":1}'::jsonb,
    '2026-01-01 00:00:00+00',
    '2026-01-01 00:00:01+00',
    '2026-01-01 00:00:02+00',
    '2026-01-01 00:00:02+00',
    20,
    20,
    'demo_seed',
    true
)
on conflict (run_uuid) do update
set status = excluded.status,
    config_snapshot = excluded.config_snapshot,
    config_hash = excluded.config_hash,
    config_revision_map = excluded.config_revision_map,
    submitted_at = excluded.submitted_at,
    started_at = excluded.started_at,
    completed_at = excluded.completed_at,
    published_at = excluded.published_at,
    jobs_considered = excluded.jobs_considered,
    jobs_matched = excluded.jobs_matched,
    worker_id = excluded.worker_id,
    is_current_result = excluded.is_current_result;

insert into public.user_pipeline_run_events (
    event_uuid,
    run_uuid,
    user_uuid,
    event_level,
    event_type,
    message,
    created_at
)
values (
    '00000000-0000-4000-8000-000000000022',
    '00000000-0000-4000-8000-000000000021',
    '00000000-0000-4000-8000-000000000020',
    'info',
    'demo_seed_completed',
    'Fixed Demo results are ready.',
    '2026-01-01 00:00:02+00'
)
on conflict (event_uuid) do nothing;

create temporary table careersignals_demo_seed_jobs (
    job_id text primary key,
    title text not null,
    company_name text not null,
    location text not null,
    location_group text not null,
    industry text not null,
    seniority text not null,
    work_arrangement text not null,
    visa_signal text not null,
    salary_min numeric not null,
    salary_max numeric not null,
    posted_at timestamptz not null,
    category_name text not null,
    match_score numeric not null
) on commit drop;

insert into careersignals_demo_seed_jobs values
    ('demo-job-001', 'Senior Data Scientist', 'Northstar Labs', 'Remote, US', 'Remote', 'technology', 'Senior', 'Remote', 'Positive', 145000, 185000, '2025-12-30 14:00:00+00', 'Data Science', 94),
    ('demo-job-002', 'Product Data Scientist', 'Beacon Software', 'New York, NY', 'Northeast', 'software', 'Mid-level', 'Hybrid', 'Unknown', 135000, 170000, '2025-12-29 15:00:00+00', 'Data Science', 92),
    ('demo-job-003', 'Healthcare Data Scientist', 'Harbor Health', 'Philadelphia, PA', 'Northeast', 'healthcare', 'Senior', 'Hybrid', 'Positive', 130000, 165000, '2025-12-28 16:00:00+00', 'Healthcare Analytics', 91),
    ('demo-job-004', 'Clinical Analytics Scientist', 'Cedar Clinical', 'Boston, MA', 'Northeast', 'healthcare', 'Mid-level', 'Remote', 'Unknown', 120000, 155000, '2025-12-27 17:00:00+00', 'Healthcare Analytics', 88),
    ('demo-job-005', 'Senior Analytics Engineer', 'Metric Works', 'Remote, US', 'Remote', 'SaaS', 'Senior', 'Remote', 'Positive', 140000, 180000, '2025-12-26 18:00:00+00', 'Analytics Engineering', 93),
    ('demo-job-006', 'Analytics Engineer', 'Lakehouse Systems', 'Austin, TX', 'South', 'data platform', 'Mid-level', 'Hybrid', 'Unknown', 125000, 160000, '2025-12-25 19:00:00+00', 'Analytics Engineering', 89),
    ('demo-job-007', 'BI Engineer', 'Clearview Cloud', 'Seattle, WA', 'West', 'cloud', 'Senior', 'Remote', 'Positive', 135000, 175000, '2025-12-24 20:00:00+00', 'Analytics Engineering', 87),
    ('demo-job-008', 'Senior BI Analyst', 'Union Street Bank', 'Wilmington, DE', 'Northeast', 'banking', 'Senior', 'Hybrid', 'Unknown', 110000, 140000, '2025-12-23 14:00:00+00', 'Business Intelligence', 90),
    ('demo-job-009', 'Business Intelligence Analyst', 'Pioneer Credit', 'Charlotte, NC', 'South', 'financial services', 'Mid-level', 'Hybrid', 'Negative', 100000, 130000, '2025-12-22 15:00:00+00', 'Business Intelligence', 84),
    ('demo-job-010', 'Reporting Analytics Lead', 'Summit Finance', 'Chicago, IL', 'Midwest', 'banking', 'Senior', 'On-site', 'Unknown', 120000, 150000, '2025-12-21 16:00:00+00', 'Business Intelligence', 82),
    ('demo-job-011', 'Credit Risk Analyst', 'Blue River Lending', 'New York, NY', 'Northeast', 'consumer lending', 'Mid-level', 'Hybrid', 'Unknown', 115000, 145000, '2025-12-20 17:00:00+00', 'Risk Analytics', 91),
    ('demo-job-012', 'Senior Risk Analytics Analyst', 'Keystone Fintech', 'Remote, US', 'Remote', 'fintech', 'Senior', 'Remote', 'Positive', 130000, 165000, '2025-12-19 18:00:00+00', 'Risk Analytics', 90),
    ('demo-job-013', 'Fraud Strategy Analyst', 'Signal Payments', 'San Francisco, CA', 'West', 'payments', 'Mid-level', 'Hybrid', 'Unknown', 125000, 155000, '2025-12-18 19:00:00+00', 'Risk Analytics', 89),
    ('demo-job-014', 'Credit Strategy Manager', 'Atlas Card', 'McLean, VA', 'Mid-Atlantic', 'credit card', 'Senior', 'Hybrid', 'Negative', 135000, 170000, '2025-12-17 20:00:00+00', 'Risk Analytics', 85),
    ('demo-job-015', 'Machine Learning Data Scientist', 'Orbit AI', 'Remote, US', 'Remote', 'AI', 'Senior', 'Remote', 'Positive', 155000, 200000, '2025-12-16 14:00:00+00', 'Machine Learning', 95),
    ('demo-job-016', 'Applied ML Scientist', 'Juniper Intelligence', 'San Jose, CA', 'West', 'AI', 'Mid-level', 'Hybrid', 'Unknown', 145000, 190000, '2025-12-15 15:00:00+00', 'Machine Learning', 90),
    ('demo-job-017', 'NLP Data Scientist', 'Verity Language Labs', 'Remote, US', 'Remote', 'technology', 'Mid-level', 'Remote', 'Positive', 140000, 180000, '2025-12-14 16:00:00+00', 'Machine Learning', 88),
    ('demo-job-018', 'Experimentation Data Scientist', 'Copper Product', 'Denver, CO', 'Mountain', 'software', 'Mid-level', 'Hybrid', 'Unknown', 130000, 165000, '2025-12-13 17:00:00+00', 'Product Analytics', 89),
    ('demo-job-019', 'Product Analytics Lead', 'Canvas Commerce', 'Remote, US', 'Remote', 'SaaS', 'Senior', 'Remote', 'Positive', 145000, 180000, '2025-12-12 18:00:00+00', 'Product Analytics', 87),
    ('demo-job-020', 'Decision Science Analyst', 'Acorn Marketplace', 'Washington, DC', 'Mid-Atlantic', 'technology', 'Mid-level', 'Hybrid', 'Unknown', 120000, 150000, '2025-12-11 19:00:00+00', 'Product Analytics', 83);

insert into public.job_postings (
    job_id,
    source_name,
    source_job_id,
    title,
    company_name,
    location,
    location_group,
    industry,
    seniority,
    work_arrangement,
    visa_signal,
    salary_min,
    salary_max,
    salary_currency,
    posted_at,
    apply_url,
    job_description,
    job_description_hash,
    first_seen_at,
    last_seen_at,
    is_active,
    updated_at
)
select
    job_id,
    'demo_seed',
    job_id,
    title,
    company_name,
    location,
    location_group,
    industry,
    seniority,
    work_arrangement,
    visa_signal,
    salary_min,
    salary_max,
    'usd',
    posted_at,
    'https://example.com/careers/' || job_id,
    'Curated CareerSignals Demo role for product evaluation. This posting is fixed and read-only.',
    md5(job_id || '|careersignals-demo'),
    '2026-01-01 00:00:00+00',
    '2026-01-01 00:00:00+00',
    true,
    '2026-01-01 00:00:00+00'
from careersignals_demo_seed_jobs
on conflict (job_id) do update
set source_name = excluded.source_name,
    source_job_id = excluded.source_job_id,
    title = excluded.title,
    company_name = excluded.company_name,
    location = excluded.location,
    location_group = excluded.location_group,
    industry = excluded.industry,
    seniority = excluded.seniority,
    work_arrangement = excluded.work_arrangement,
    visa_signal = excluded.visa_signal,
    salary_min = excluded.salary_min,
    salary_max = excluded.salary_max,
    salary_currency = excluded.salary_currency,
    posted_at = excluded.posted_at,
    apply_url = excluded.apply_url,
    job_description = excluded.job_description,
    job_description_hash = excluded.job_description_hash,
    first_seen_at = excluded.first_seen_at,
    last_seen_at = excluded.last_seen_at,
    is_active = excluded.is_active;

insert into public.user_job_matches (
    user_uuid,
    job_id,
    run_uuid,
    category_name,
    match_score,
    title_score,
    required_skill_score,
    preferred_skill_score,
    industry_score,
    salary_score,
    work_arrangement_score,
    visa_score,
    matched_skills,
    missing_skills,
    ranking_reasons,
    is_top_match,
    is_current,
    created_at
)
select
    '00000000-0000-4000-8000-000000000020',
    job_id,
    '00000000-0000-4000-8000-000000000021',
    category_name,
    match_score,
    least(100, match_score + 3),
    least(100, match_score + 1),
    greatest(0, match_score - 5),
    least(100, match_score + 2),
    greatest(0, match_score - 4),
    least(100, match_score + 1),
    case visa_signal when 'Positive' then 100 when 'Negative' then 25 else 60 end,
    '["Python","SQL"]'::jsonb,
    '["Domain-specific platform tooling"]'::jsonb,
    jsonb_build_array('Strong alignment with the fixed Demo candidate profile'),
    match_score >= 80,
    true,
    '2026-01-01 00:00:02+00'
from careersignals_demo_seed_jobs
on conflict (user_uuid, job_id, run_uuid) do update
set category_name = excluded.category_name,
    match_score = excluded.match_score,
    title_score = excluded.title_score,
    required_skill_score = excluded.required_skill_score,
    preferred_skill_score = excluded.preferred_skill_score,
    industry_score = excluded.industry_score,
    salary_score = excluded.salary_score,
    work_arrangement_score = excluded.work_arrangement_score,
    visa_score = excluded.visa_score,
    matched_skills = excluded.matched_skills,
    missing_skills = excluded.missing_skills,
    ranking_reasons = excluded.ranking_reasons,
    is_top_match = excluded.is_top_match,
    is_current = excluded.is_current;

insert into public.user_category_summary (
    user_uuid,
    run_uuid,
    category_name,
    metrics,
    is_current
)
select
    '00000000-0000-4000-8000-000000000020',
    '00000000-0000-4000-8000-000000000021',
    category_name,
    jsonb_build_object(
        'jobs_found', count(*),
        'average_match_score', round(avg(match_score), 1),
        'top_matches', count(*) filter (where match_score >= 80)
    ),
    true
from careersignals_demo_seed_jobs
group by category_name
on conflict (user_uuid, run_uuid, category_name) do update
set metrics = excluded.metrics,
    is_current = excluded.is_current;

insert into public.user_skill_gap (
    user_uuid,
    run_uuid,
    canonical_skill,
    metrics,
    is_current
)
values
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'Airflow', '{"appears_in_job_count":7,"gap_priority":"High"}', true),
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'Databricks', '{"appears_in_job_count":6,"gap_priority":"High"}', true),
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'Looker', '{"appears_in_job_count":5,"gap_priority":"Medium"}', true),
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'Kafka', '{"appears_in_job_count":4,"gap_priority":"Medium"}', true),
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'Fivetran', '{"appears_in_job_count":3,"gap_priority":"Low"}', true),
    ('00000000-0000-4000-8000-000000000020', '00000000-0000-4000-8000-000000000021', 'SAS', '{"appears_in_job_count":2,"gap_priority":"Low"}', true)
on conflict (user_uuid, run_uuid, canonical_skill) do update
set metrics = excluded.metrics,
    is_current = excluded.is_current;

insert into public.user_company_priority (
    user_uuid,
    run_uuid,
    company_name,
    metrics,
    is_current
)
select
    '00000000-0000-4000-8000-000000000020',
    '00000000-0000-4000-8000-000000000021',
    company_name,
    jsonb_build_object(
        'matching_roles_count', count(*),
        'highest_match_score', max(match_score),
        'average_match_score', round(avg(match_score), 1),
        'priority', case when max(match_score) >= 90 then 'High' else 'Medium' end
    ),
    true
from careersignals_demo_seed_jobs
group by company_name
on conflict (user_uuid, run_uuid, company_name) do update
set metrics = excluded.metrics,
    is_current = excluded.is_current;

update public.user_profiles
set last_successful_pipeline_run_uuid = '00000000-0000-4000-8000-000000000021'
where user_uuid = '00000000-0000-4000-8000-000000000020';

-- Demo analytics stays fixture-scoped. The API maps this tenant's global
-- series to its fixed match universe instead of exposing production history.
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
    '00000000-0000-4000-8000-000000000020',
    (now() at time zone 'America/New_York')::date,
    count(distinct matches.job_id)::integer,
    0,
    0,
    '00000000-0000-4000-8000-000000000021',
    now()
from public.user_job_matches as matches
where matches.user_uuid = '00000000-0000-4000-8000-000000000020'
  and matches.is_current = true
on conflict (user_uuid, metric_date) do update set
    user_jobs_count = excluded.user_jobs_count,
    applied_jobs_count = excluded.applied_jobs_count,
    interview_jobs_count = excluded.interview_jobs_count,
    personal_run_uuid = excluded.personal_run_uuid,
    recorded_at = excluded.recorded_at;

do $assertion$
declare
    current_demo_jobs integer;
begin
    select count(*)
    into current_demo_jobs
    from public.user_job_matches
    where user_uuid = '00000000-0000-4000-8000-000000000020'
      and is_current;

    if current_demo_jobs <> 20 then
        raise exception 'Demo seed expected exactly 20 current jobs, found %', current_demo_jobs;
    end if;
end
$assertion$;

commit;
