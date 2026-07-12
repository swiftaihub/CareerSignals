{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key=['user_uuid', 'run_uuid', 'category_name'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'mart', 'motherduck', 'excel']
) }}

select
    user_uuid,
    run_uuid,
    category_name,
    count(*) as jobs_found,
    sum(case when match_tier = 'Excellent Match' then 1 else 0 end) as excellent_matches,
    sum(case when match_tier = 'Strong Match' then 1 else 0 end) as strong_matches,
    sum(case when match_tier = 'Good Match' then 1 else 0 end) as good_matches,
    round(avg(match_score), 1) as average_match_score,
    round(avg(salary_midpoint), 2) as average_salary_midpoint,
    sum(case when work_arrangement = 'Remote' then 1 else 0 end) as remote_count,
    sum(case when work_arrangement = 'Hybrid' then 1 else 0 end) as hybrid_count,
    sum(case when work_arrangement in ('On-site', 'Onsite') then 1 else 0 end) as onsite_count,
    sum(case when work_arrangement = 'Unknown' then 1 else 0 end) as unknown_work_arrangement_count,
    sum(case when visa_signal = 'Positive' then 1 else 0 end) as positive_visa_signal_count,
    sum(case when visa_signal = 'Negative' then 1 else 0 end) as negative_visa_signal_count,
    sum(case when visa_signal = 'Unknown' then 1 else 0 end) as unknown_visa_signal_count
from {{ ref('mart_jobs_scored') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, category_name
