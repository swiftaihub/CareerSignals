{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key=['user_uuid', 'run_uuid', 'skill'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'mart', 'motherduck', 'excel']
) }}

with counts as (
    select
        user_uuid,
        run_uuid,
        skill,
        any_value(skill_group) as skill_group,
        bool_or(in_candidate_profile) as in_candidate_profile,
        count(distinct job_id) as appears_in_job_count,
        any_value(job_title) as example_title
    from {{ ref('int_user_job_skills_exploded') }}
    where user_uuid = '{{ var("user_uuid") }}'
      and run_uuid = '{{ var("run_uuid") }}'
    group by user_uuid, run_uuid, skill
),

totals as (
    select user_uuid, run_uuid, count(distinct job_id) as total_jobs
    from {{ ref('mart_jobs_scored') }}
    where user_uuid = '{{ var("user_uuid") }}'
      and run_uuid = '{{ var("run_uuid") }}'
    group by user_uuid, run_uuid
)

select
    counts.user_uuid,
    counts.run_uuid,
    counts.skill,
    counts.skill_group,
    counts.appears_in_job_count,
    case
        when totals.total_jobs = 0 then 0
        else round(counts.appears_in_job_count::double / totals.total_jobs, 3)
    end as appears_in_job_pct,
    case when counts.in_candidate_profile then 'Yes' else 'No' end as in_candidate_profile,
    case
        when not counts.in_candidate_profile
         and (counts.appears_in_job_count >= 4 or counts.appears_in_job_count::double / nullif(totals.total_jobs, 0) >= 0.35) then 'High'
        when not counts.in_candidate_profile and counts.appears_in_job_count >= 2 then 'Medium'
        else 'Low'
    end as gap_priority,
    counts.example_title as example_matching_job_titles
from counts
inner join totals
    on counts.user_uuid = totals.user_uuid
    and counts.run_uuid = totals.run_uuid
