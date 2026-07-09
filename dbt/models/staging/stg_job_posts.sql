{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['job_id', 'run_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['staging', 'motherduck', 'incremental']
) }}

select
    job_id,
    run_id,
    source,
    category_name,
    job_title,
    normalized_title,
    company,
    industry,
    location,
    work_arrangement,
    employment_type,
    seniority,
    salary_min,
    salary_max,
    salary_midpoint,
    salary_range_text,
    date_posted,
    date_collected,
    jd_post_link,
    apply_link,
    job_description,
    required_skills,
    preferred_skills,
    all_extracted_skills,
    visa_signal,
    match_score,
    match_tier,
    reasoning_summary,
    inserted_at
from {{ source('staging', 'python_jobs_processed') }}
where job_id is not null
{% if is_incremental() %}
  and inserted_at >= coalesce((select max(inserted_at) from {{ this }}), timestamp '1900-01-01')
{% endif %}
