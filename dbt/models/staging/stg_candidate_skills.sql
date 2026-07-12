{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['user_uuid', 'run_uuid', 'skill'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'staging', 'compatibility']
) }}

select *
from {{ ref('stg_user_candidate_skills') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
