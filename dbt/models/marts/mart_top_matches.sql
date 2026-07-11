{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key=['user_uuid', 'run_uuid', 'job_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'mart', 'motherduck', 'excel']
) }}

select *
from {{ ref('mart_jobs_scored') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
  and match_score >= top_match_threshold
