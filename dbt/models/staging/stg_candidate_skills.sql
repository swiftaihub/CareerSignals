{{ config(
    materialized='incremental',
    schema='staging',
    unique_key='skill',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ careersignal_clear_incremental_model() }}",
    tags=['staging', 'motherduck', 'incremental']
) }}

select
    skill,
    skill_group,
    in_candidate_profile
from {{ source('staging', 'python_candidate_skills') }}
where skill is not null
