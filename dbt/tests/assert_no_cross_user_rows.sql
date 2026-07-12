{% do require_user_context() %}
{{ config(tags=['user']) }}

select 'mart_jobs_scored' as model_name, user_uuid, run_uuid
from {{ ref('mart_jobs_scored') }}
where run_uuid = '{{ var("run_uuid") }}'
  and user_uuid <> '{{ var("user_uuid") }}'
union all
select 'mart_top_matches', user_uuid, run_uuid
from {{ ref('mart_top_matches') }}
where run_uuid = '{{ var("run_uuid") }}'
  and user_uuid <> '{{ var("user_uuid") }}'
union all
select 'mart_category_summary', user_uuid, run_uuid
from {{ ref('mart_category_summary') }}
where run_uuid = '{{ var("run_uuid") }}'
  and user_uuid <> '{{ var("user_uuid") }}'
union all
select 'mart_skill_gap_analysis', user_uuid, run_uuid
from {{ ref('mart_skill_gap_analysis') }}
where run_uuid = '{{ var("run_uuid") }}'
  and user_uuid <> '{{ var("user_uuid") }}'
union all
select 'mart_company_priority_list', user_uuid, run_uuid
from {{ ref('mart_company_priority_list') }}
where run_uuid = '{{ var("run_uuid") }}'
  and user_uuid <> '{{ var("user_uuid") }}'
