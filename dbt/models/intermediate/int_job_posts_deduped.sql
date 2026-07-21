{% do validate_shared_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key='job_id',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    post_hook="{{ purge_unscoped_shared_rows() }}",
    tags=['shared', 'intermediate', 'motherduck']
) }}

with ranked as (
    select
        *,
        min(first_seen_at) over (partition by job_id) as canonical_first_seen_at,
        max(last_seen_at) over (partition by job_id) as canonical_last_seen_at,
        row_number() over (
            partition by job_id
            order by last_seen_at desc, inserted_at desc, connector_run_uuid desc
        ) as row_number_for_job
    from {{ ref('stg_job_posts') }}
)

select
    * exclude (
        row_number_for_job,
        first_seen_at,
        last_seen_at,
        canonical_first_seen_at,
        canonical_last_seen_at
    ),
    canonical_first_seen_at as first_seen_at,
    canonical_last_seen_at as last_seen_at
from ranked
where row_number_for_job = 1
