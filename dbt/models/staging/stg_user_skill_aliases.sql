{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['user_uuid', 'run_uuid', 'canonical_skill', 'alias'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'staging', 'motherduck']
) }}

select
    user_uuid,
    run_uuid,
    config_hash,
    canonical_skill,
    alias,
    staged_at
from {{ source('app', 'user_skill_aliases') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
  and canonical_skill is not null
  and alias is not null
