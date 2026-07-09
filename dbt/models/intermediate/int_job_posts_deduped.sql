{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key='job_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['intermediate', 'motherduck', 'incremental']
) }}

with ranked as (
    select
        *,
        row_number() over (
            partition by job_id
            order by inserted_at desc
        ) as rn
    from {{ ref('stg_job_posts') }}
)

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
from ranked
where rn = 1
