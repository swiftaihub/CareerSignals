{% do require_user_context() %}
{{ config(tags=['user']) }}

select 'mart_jobs_scored' as model_name
from {{ ref('mart_jobs_scored') }}
where user_uuid is null or run_uuid is null
union all
select 'mart_top_matches'
from {{ ref('mart_top_matches') }}
where user_uuid is null or run_uuid is null
union all
select 'mart_category_summary'
from {{ ref('mart_category_summary') }}
where user_uuid is null or run_uuid is null
union all
select 'mart_skill_gap_analysis'
from {{ ref('mart_skill_gap_analysis') }}
where user_uuid is null or run_uuid is null
union all
select 'mart_company_priority_list'
from {{ ref('mart_company_priority_list') }}
where user_uuid is null or run_uuid is null
