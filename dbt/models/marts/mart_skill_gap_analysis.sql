{{ config(
    materialized='incremental',
    schema='mart',
    unique_key='skill',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['mart', 'motherduck', 'incremental', 'excel']
) }}

with counts as (
    select
        skill,
        skill_group,
        in_candidate_profile,
        count(distinct job_id) as appears_in_job_count,
        any_value(job_title) as example_title
    from {{ ref('int_job_skills_exploded') }}
    group by skill, skill_group, in_candidate_profile
),

totals as (
    select count(distinct job_id) as total_jobs
    from {{ ref('mart_jobs_scored') }}
)

select
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
            and (
                counts.appears_in_job_count >= 4
                or counts.appears_in_job_count::double / nullif(totals.total_jobs, 0) >= 0.35
            )
            then 'High'
        when not counts.in_candidate_profile and counts.appears_in_job_count >= 2 then 'Medium'
        else 'Low'
    end as gap_priority,
    counts.example_title as example_matching_job_titles
from counts
cross join totals
order by appears_in_job_count desc, skill
