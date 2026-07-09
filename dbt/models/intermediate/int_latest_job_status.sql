{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_id', 'job_id'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['intermediate', 'motherduck', 'incremental']
) }}

with ranked as (
    select
        *,
        row_number() over (
            partition by user_id, job_id
            order by updated_at desc
        ) as rn
    from {{ ref('stg_application_status') }}
)

select
    user_id,
    job_id,
    application_status,
    notes,
    updated_at
from ranked
where rn = 1
