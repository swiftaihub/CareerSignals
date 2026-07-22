{% do require_user_context() %}
{{ config(tags=['user']) }}

select user_uuid, run_uuid, company
from {{ ref('mart_company_priority_list') }}
where user_uuid = '{{ var("user_uuid") }}'
  and run_uuid = '{{ var("run_uuid") }}'
  and nullif(trim(company), '') is null
