{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['user_uuid', 'run_uuid', 'job_id', 'updated_at'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'staging', 'motherduck']
) }}

select
    coalesce(user_uuid, user_id) as user_uuid,
    '{{ var("run_uuid") }}' as run_uuid,
    job_id,
    application_status,
    notes,
    updated_at
from {{ source('app', 'job_application_status') }}
where coalesce(user_uuid, user_id) = '{{ var("user_uuid") }}'
  and job_id is not null
