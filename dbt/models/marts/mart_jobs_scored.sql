{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key=['user_uuid', 'run_uuid', 'job_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'mart', 'motherduck', 'excel']
) }}

with ranked as (
    select
        scored.*,
        row_number() over (
            partition by scored.user_uuid, scored.run_uuid, scored.job_id
            order by scored.match_score desc, scored.category_name
        ) as score_row_number
    from {{ ref('int_user_jobs_scored') }} scored
    where scored.user_uuid = '{{ var("user_uuid") }}'
      and scored.run_uuid = '{{ var("run_uuid") }}'
)

select
    ranked.user_uuid,
    ranked.run_uuid,
    ranked.config_hash,
    ranked.job_id,
    ranked.connector_run_uuid,
    ranked.category_name,
    ranked.match_tier,
    ranked.match_score,
    ranked.title_score,
    ranked.skill_score,
    ranked.skill_score as required_skill_score,
    cast(null as double) as preferred_skill_score,
    ranked.industry_score,
    ranked.salary_score,
    ranked.work_arrangement_score,
    ranked.visa_score,
    ranked.job_title,
    ranked.normalized_title,
    ranked.company,
    ranked.industry,
    ranked.location,
    ranked.location_normalized,
    ranked.location_group,
    ranked.work_arrangement,
    ranked.seniority,
    ranked.employment_type,
    ranked.salary_range_text,
    ranked.salary_min,
    ranked.salary_max,
    ranked.salary_midpoint,
    ranked.visa_signal,
    ranked.visa_status,
    ranked.visa_evidence,
    ranked.visa_confidence,
    ranked.required_skills,
    ranked.preferred_skills,
    ranked.all_extracted_skills,
    ranked.matched_candidate_skills as matched_skills,
    ranked.missing_candidate_skills as missing_skills,
    ranked.jd_post_link,
    ranked.apply_link,
    ranked.date_posted,
    ranked.posted_at,
    ranked.date_collected,
    ranked.source,
    coalesce(status.application_status, 'Not Applied') as application_status,
    status.notes as application_notes,
    ranked.reasoning_summary,
    cast(to_json([ranked.reasoning_summary]) as varchar) as ranking_reasons,
    ranked.top_match_threshold,
    ranked.last_seen_at as inserted_at
from ranked
left join {{ ref('int_latest_job_status') }} status
    on ranked.user_uuid = status.user_uuid
    and ranked.run_uuid = status.run_uuid
    and ranked.job_id = status.job_id
where ranked.score_row_number = 1
