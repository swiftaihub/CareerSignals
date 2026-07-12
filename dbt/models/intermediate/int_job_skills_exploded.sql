{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_uuid', 'run_uuid', 'job_id', 'category_name', 'skill'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'intermediate', 'compatibility']
) }}

select *
from {{ ref('int_user_job_skills_exploded') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
