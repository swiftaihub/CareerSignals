{% do require_user_context() %}
{{ config(tags=['user']) }}

select user_uuid, run_uuid, job_id, count(*) as duplicate_count
from {{ ref('mart_jobs_scored') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, job_id
having count(*) > 1
union all
select user_uuid, run_uuid, job_id, count(*) as duplicate_count
from {{ ref('mart_top_matches') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, job_id
having count(*) > 1
union all
select user_uuid, run_uuid, category_name as job_id, count(*) as duplicate_count
from {{ ref('mart_category_summary') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, category_name
having count(*) > 1
union all
select user_uuid, run_uuid, skill as job_id, count(*) as duplicate_count
from {{ ref('mart_skill_gap_analysis') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, skill
having count(*) > 1
union all
select user_uuid, run_uuid, company as job_id, count(*) as duplicate_count
from {{ ref('mart_company_priority_list') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
group by user_uuid, run_uuid, company
having count(*) > 1
