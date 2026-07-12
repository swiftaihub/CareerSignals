{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_uuid', 'run_uuid', 'job_id', 'category_name'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'intermediate', 'motherduck']
) }}

select
    preferences.user_uuid,
    preferences.run_uuid,
    preferences.config_hash,
    jobs.job_id,
    jobs.connector_run_uuid,
    jobs.source,
    jobs.source_job_id,
    preferences.category_name,
    jobs.category_name as shared_category_name,
    jobs.job_title,
    jobs.normalized_title,
    jobs.company,
    jobs.normalized_company,
    jobs.industry,
    jobs.location,
    jobs.location_normalized,
    jobs.location_group,
    jobs.work_arrangement,
    jobs.employment_type,
    jobs.seniority,
    jobs.salary_min,
    jobs.salary_max,
    jobs.salary_midpoint,
    jobs.salary_range_text,
    jobs.date_posted,
    jobs.posted_at,
    jobs.date_collected,
    jobs.jd_post_link,
    jobs.apply_link,
    jobs.job_description,
    jobs.normalized_description,
    jobs.visa_signal,
    jobs.visa_status,
    jobs.visa_evidence,
    jobs.visa_confidence,
    jobs.first_seen_at,
    jobs.last_seen_at,
    preferences.search_titles,
    preferences.industries,
    preferences.target_titles,
    preferences.target_industries,
    preferences.min_base_salary,
    preferences.preferred_base_salary,
    preferences.title_match_weight,
    preferences.required_skill_match_weight,
    preferences.industry_match_weight,
    preferences.salary_match_weight,
    preferences.work_arrangement_match_weight,
    preferences.visa_signal_match_weight,
    preferences.top_match_threshold
from {{ ref('int_job_posts_deduped') }} as jobs
cross join {{ ref('stg_user_job_preferences') }} as preferences
where preferences.user_uuid = '{{ var("user_uuid") }}'
  and preferences.run_uuid = '{{ var("run_uuid") }}'
  and jobs.connector_run_uuid = '{{ var("connector_run_uuid", "") }}'
  and (
      lower(jobs.category_name) = lower(preferences.category_name)
      or exists (
          select 1
          from json_each(preferences.search_titles) as configured_title
          where strpos(
              lower(jobs.normalized_title),
              lower(trim(both '"' from cast(configured_title.value as varchar)))
          ) > 0
      )
  )
  and (
      json_array_length(preferences.locations) = 0
      or exists (
          select 1
          from json_each(preferences.locations) as configured_location
          where {{ candidate_location_matches(
              'jobs.location',
              'jobs.location_normalized',
              'jobs.location_group',
              'jobs.work_arrangement',
              'trim(both \'"\' from cast(configured_location.value as varchar))'
          ) }}
      )
  )
  and (
      json_array_length(preferences.employment_types) = 0
      or exists (
          select 1
          from json_each(preferences.employment_types) as configured_employment
          where lower(jobs.employment_type) = lower(trim(both '"' from cast(configured_employment.value as varchar)))
      )
  )
  and not exists (
      select 1
      from json_each(preferences.excluded_companies) as excluded_company
      where lower(jobs.company) like '%' || lower(trim(both '"' from cast(excluded_company.value as varchar))) || '%'
  )
  and not exists (
      select 1
      from json_each(preferences.excluded_titles) as excluded_title
      where lower(jobs.job_title) like '%' || lower(trim(both '"' from cast(excluded_title.value as varchar))) || '%'
  )
