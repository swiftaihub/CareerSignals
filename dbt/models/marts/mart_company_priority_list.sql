{{ config(
    materialized='incremental',
    schema='mart',
    unique_key='company',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['mart', 'motherduck', 'incremental', 'excel']
) }}

with company_rollup as (
    select
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
    group by company
)

select
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
order by
    case priority when 'High' then 1 when 'Medium' then 2 else 3 end,
    highest_match_score desc
