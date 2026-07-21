{% do validate_shared_context() %}
{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['job_id', 'connector_run_uuid'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    post_hook="{{ purge_unscoped_shared_rows() }}",
    tags=['shared', 'staging', 'motherduck']
) }}

select
    job_id,
    connector_run_uuid,
    source,
    source_job_id,
    category_name,
    job_title,
    normalized_title,
    company,
    normalized_company,
    industry,
    location,
    location_normalized,
    location_group,
    work_arrangement,
    employment_type,
    seniority,
    salary_min,
    salary_max,
    salary_midpoint,
    salary_range_text,
    date_posted,
    posted_at,
    date_collected,
    jd_post_link,
    apply_link,
    job_description,
    normalized_description,
    visa_signal,
    visa_status,
    visa_evidence,
    visa_confidence,
    first_seen_at,
    last_seen_at,
    inserted_at
from {{ source('staging', 'shared_jobs_processed') }}
where job_id is not null
  and connector_run_uuid is not null
{% set connector_run_uuid = var('connector_run_uuid', none) %}
{% if connector_run_uuid is not none and connector_run_uuid | string | trim != '' %}
  and connector_run_uuid = '{{ connector_run_uuid }}'
{% endif %}
{% if is_incremental() %}
  and inserted_at >= coalesce((select max(inserted_at) from {{ this }}), timestamp '1900-01-01')
{% endif %}
