{% do validate_shared_context() %}
{{ config(
    materialized='incremental',
    schema='mart',
    unique_key='source',
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    post_hook="{{ purge_unscoped_shared_rows() }}",
    tags=['shared', 'mart', 'motherduck']
) }}

select
    source,
    max(last_seen_at) as last_refreshed_at,
    max_by(connector_run_uuid, last_seen_at) as connector_run_uuid,
    count(distinct job_id) as active_job_count
from {{ ref('int_job_posts_deduped') }}
group by source
