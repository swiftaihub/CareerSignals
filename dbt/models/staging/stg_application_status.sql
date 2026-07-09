{{ config(
    materialized='incremental',
    schema='staging',
    unique_key=['user_id', 'job_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    tags=['staging', 'motherduck', 'incremental']
) }}

select
    user_id,
    job_id,
    application_status,
    notes,
    updated_at
from {{ source('app', 'job_application_status') }}
where job_id is not null
{% if is_incremental() %}
  and updated_at >= coalesce((select max(updated_at) from {{ this }}), timestamp '1900-01-01')
{% endif %}
