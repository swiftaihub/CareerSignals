{% do require_user_context() %}
{{ config(tags=['user']) }}

select results.user_uuid, results.run_uuid, results.job_id
from {{ ref('mart_jobs_scored') }} results
left join {{ ref('mart_shared_canonical_jobs') }} shared
    on results.job_id = shared.job_id
where results.user_uuid = '{{ var("user_uuid") }}'
  and results.run_uuid = '{{ var("run_uuid") }}'
  and shared.job_id is null
