{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key=['user_uuid', 'run_uuid', 'company'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'mart', 'motherduck', 'excel']
) }}

with company_rollup as (
    select
        user_uuid,
        run_uuid,
        company,
        any_value(industry) as industry,
        count(*) as matching_roles_count,
        round(avg(match_score), 1) as average_match_score,
        max(match_score) as highest_match_score,
        round(avg(salary_midpoint), 2) as average_salary_midpoint,
        arg_max(job_title, match_score) as best_matching_role,
        sum(case when match_tier = 'Excellent Match' then 1 else 0 end) as excellent_count,
        sum(case when match_tier = 'Strong Match' then 1 else 0 end) as strong_count,
        sum(case when match_tier in ('Good Match', 'Strong Match') then 1 else 0 end) as good_or_strong_count,
        string_agg(distinct visa_signal, ', ') as visa_signal_summary
    from {{ ref('mart_jobs_scored') }}
    where user_uuid = '{{ var("user_uuid") }}'
      and run_uuid = '{{ var("run_uuid") }}'
      and nullif(trim(company), '') is not null
    group by user_uuid, run_uuid, company
)

select
    user_uuid,
    run_uuid,
    company,
    industry,
    matching_roles_count,
    average_match_score,
    highest_match_score,
    average_salary_midpoint,
    best_matching_role,
    visa_signal_summary,
    case
        when excellent_count >= 1 or strong_count >= 2 then 'High'
        when good_or_strong_count >= 1 then 'Medium'
        else 'Low'
    end as priority
from company_rollup
