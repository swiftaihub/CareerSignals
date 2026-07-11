{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_uuid', 'run_uuid', 'job_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'intermediate', 'motherduck']
) }}

with ranked as (
    select
        *,
        row_number() over (
            partition by user_uuid, run_uuid, job_id
            order by updated_at desc nulls last
        ) as status_row_number
    from {{ ref('stg_application_status') }}
    where user_uuid = '{{ var("user_uuid") }}'
      and run_uuid = '{{ var("run_uuid") }}'
)

select * exclude (status_row_number)
from ranked
where status_row_number = 1
