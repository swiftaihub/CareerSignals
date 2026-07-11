{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_uuid', 'run_uuid', 'job_id', 'category_name', 'skill'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'intermediate', 'motherduck']
) }}

select distinct
    candidates.user_uuid,
    candidates.run_uuid,
    candidates.config_hash,
    candidates.job_id,
    candidates.category_name,
    candidates.job_title,
    aliases.canonical_skill as skill,
    coalesce(candidate_skills.skill_group, 'Market Skill') as skill_group,
    candidate_skills.skill is not null as in_candidate_profile
from {{ ref('int_user_job_candidates') }} as candidates
inner join {{ ref('stg_user_skill_aliases') }} as aliases
    on candidates.user_uuid = aliases.user_uuid
    and candidates.run_uuid = aliases.run_uuid
    and length(trim(aliases.alias)) >= 2
    and strpos(lower(candidates.normalized_description), lower(trim(aliases.alias))) > 0
left join {{ ref('stg_user_candidate_skills') }} as candidate_skills
    on candidates.user_uuid = candidate_skills.user_uuid
    and candidates.run_uuid = candidate_skills.run_uuid
    and lower(aliases.canonical_skill) = lower(candidate_skills.skill)
where candidates.user_uuid = '{{ var("user_uuid") }}'
  and candidates.run_uuid = '{{ var("run_uuid") }}'
