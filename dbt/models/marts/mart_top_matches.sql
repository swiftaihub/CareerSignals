{{ config(
    materialized='incremental',
    schema='mart',
    unique_key='job_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['mart', 'motherduck', 'incremental', 'excel']
) }}

select *
from {{ ref('mart_jobs_scored') }}
where match_score >= 80
order by match_score desc, salary_midpoint desc nulls last
