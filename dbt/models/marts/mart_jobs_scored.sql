{{ config(
    materialized='incremental',
    schema='mart',
    unique_key='job_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['mart', 'motherduck', 'incremental', 'excel']
) }}

select
    jobs.job_id,
    jobs.category_name,
    jobs.match_tier,
    jobs.match_score,
    jobs.job_title,
    jobs.normalized_title,
    jobs.company,
    jobs.industry,
    jobs.location,
    jobs.location_normalized,
    jobs.location_group,
    jobs.work_arrangement,
    jobs.seniority,
    jobs.employment_type,
    jobs.salary_range_text,
    jobs.salary_min,
    jobs.salary_max,
    jobs.salary_midpoint,
    jobs.visa_signal,
    coalesce(
        jobs.visa_status,
        case
            when jobs.visa_signal = 'Positive' then 'Sponsorship Available'
            when jobs.visa_signal = 'Negative' then 'No Sponsorship'
            else 'Unknown'
        end
    ) as visa_status,
    jobs.visa_evidence,
    coalesce(jobs.visa_confidence, 'Low') as visa_confidence,
    jobs.required_skills,
    jobs.preferred_skills,
    jobs.all_extracted_skills,
    jobs.jd_post_link,
    jobs.apply_link,
    jobs.date_posted,
    jobs.date_collected,
    jobs.source,
    coalesce(status.application_status, 'Not Applied') as application_status,
    jobs.reasoning_summary,
    jobs.run_id,
    jobs.inserted_at
from {{ ref('int_job_posts_deduped') }} as jobs
left join {{ ref('int_latest_job_status') }} as status
    on jobs.job_id = status.job_id
    and status.user_id = 'personal_user'
