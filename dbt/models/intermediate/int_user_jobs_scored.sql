{% do require_user_context() %}
{{ config(
    materialized='incremental',
    schema='intermediate',
    unique_key=['user_uuid', 'run_uuid', 'job_id', 'category_name'],
    incremental_strategy='delete+insert',
    on_schema_change='sync_all_columns',
    pre_hook="{{ delete_user_partition() }}",
    post_hook="{{ purge_unscoped_user_rows() }}",
    tags=['user', 'intermediate', 'motherduck']
) }}

with skill_rollup as (
    select
        user_uuid,
        run_uuid,
        job_id,
        category_name,
        count(distinct skill) as extracted_skill_count,
        count(distinct case when in_candidate_profile then skill end) as matched_skill_count,
        cast(to_json(list(distinct skill order by skill)) as varchar) as all_extracted_skills,
        cast(to_json(list(distinct skill order by skill) filter (where in_candidate_profile)) as varchar) as matched_candidate_skills,
        cast(to_json(list(distinct skill order by skill) filter (where not in_candidate_profile)) as varchar) as missing_candidate_skills
    from {{ ref('int_user_job_skills_exploded') }}
    where user_uuid = '{{ var("user_uuid") }}'
      and run_uuid = '{{ var("run_uuid") }}'
    group by user_uuid, run_uuid, job_id, category_name
),

component_scores as (
    select
        candidates.*,
        coalesce((
            select max(
                case
                    when lower(candidates.job_title) = lower(configured_title.title) then 100.0
                    when strpos(lower(candidates.job_title), lower(configured_title.title)) > 0
                      or strpos(lower(configured_title.title), lower(candidates.job_title)) > 0 then 90.0
                    else 0.0
                end
            )
            from (
                select trim(both '"' from cast(value as varchar)) as title
                from json_each(candidates.search_titles)
                union all
                select trim(both '"' from cast(value as varchar)) as title
                from json_each(candidates.target_titles)
            ) as configured_title
        ), 0.0) as title_score,
        case
            when coalesce(skills.extracted_skill_count, 0) = 0 then 40.0
            else least(100.0, skills.matched_skill_count::double / skills.extracted_skill_count * 100.0)
        end as skill_score,
        case
            when candidates.industry is null or candidates.industry = '' or candidates.industry = 'Unknown' then 40.0
            when exists (
                select 1 from (
                    select trim(both '"' from cast(value as varchar)) as industry from json_each(candidates.industries)
                    union all
                    select trim(both '"' from cast(value as varchar)) as industry from json_each(candidates.target_industries)
                ) configured_industry
                where lower(candidates.industry) = lower(configured_industry.industry)
            ) then 100.0
            when exists (
                select 1 from (
                    select trim(both '"' from cast(value as varchar)) as industry from json_each(candidates.industries)
                    union all
                    select trim(both '"' from cast(value as varchar)) as industry from json_each(candidates.target_industries)
                ) configured_industry
                where strpos(lower(candidates.industry), lower(configured_industry.industry)) > 0
                   or strpos(lower(configured_industry.industry), lower(candidates.industry)) > 0
            ) then 90.0
            else 40.0
        end as industry_score,
        case
            when candidates.salary_midpoint is null then 50.0
            when candidates.preferred_base_salary > 0
             and candidates.salary_midpoint >= candidates.preferred_base_salary then 100.0
            when candidates.min_base_salary > 0
             and candidates.salary_midpoint >= candidates.min_base_salary then
                75.0 + least(
                    25.0,
                    (candidates.salary_midpoint - candidates.min_base_salary)
                    / greatest(candidates.preferred_base_salary - candidates.min_base_salary, 1.0)
                    * 25.0
                )
            when candidates.min_base_salary > 0 then
                greatest(0.0, least(70.0, candidates.salary_midpoint / candidates.min_base_salary * 70.0))
            else 50.0
        end as salary_score,
        case
            when candidates.work_arrangement is null or candidates.work_arrangement = 'Unknown' then 50.0
            when exists (
                select 1
                from {{ ref('stg_user_job_preferences') }} preferences,
                     json_each(preferences.work_arrangements) configured_work
                where preferences.user_uuid = candidates.user_uuid
                  and preferences.run_uuid = candidates.run_uuid
                  and preferences.category_name = candidates.category_name
                  and lower(candidates.work_arrangement) = lower(trim(both '"' from cast(configured_work.value as varchar)))
            ) then 100.0
            when lower(candidates.work_arrangement) in ('on-site', 'onsite') then 20.0
            else 50.0
        end as work_arrangement_score,
        case
            when lower(candidates.visa_signal) = 'positive' then 100.0
            when lower(candidates.visa_signal) = 'negative' then 10.0
            else 60.0
        end as visa_score,
        coalesce(skills.all_extracted_skills, '[]') as all_extracted_skills,
        coalesce(skills.matched_candidate_skills, '[]') as matched_candidate_skills,
        coalesce(skills.missing_candidate_skills, '[]') as missing_candidate_skills
    from {{ ref('int_user_job_candidates') }} candidates
    left join skill_rollup skills
        on candidates.user_uuid = skills.user_uuid
        and candidates.run_uuid = skills.run_uuid
        and candidates.job_id = skills.job_id
        and candidates.category_name = skills.category_name
    where candidates.user_uuid = '{{ var("user_uuid") }}'
      and candidates.run_uuid = '{{ var("run_uuid") }}'
),

weighted as (
    select
        *,
        round(
            (
                title_score * title_match_weight
                + skill_score * required_skill_match_weight
                + industry_score * industry_match_weight
                + salary_score * salary_match_weight
                + work_arrangement_score * work_arrangement_match_weight
                + visa_score * visa_signal_match_weight
            ) / nullif(
                title_match_weight + required_skill_match_weight + industry_match_weight
                + salary_match_weight + work_arrangement_match_weight + visa_signal_match_weight,
                0
            ),
            1
        ) as match_score
    from component_scores
)

select
    *,
    case
        when match_score >= 90 then 'Excellent Match'
        when match_score >= 80 then 'Strong Match'
        when match_score >= 70 then 'Good Match'
        when match_score >= 60 then 'Possible Match'
        else 'Low Priority'
    end as match_tier,
    matched_candidate_skills as required_skills,
    '[]' as preferred_skills,
    case
        when match_score >= 80 then 'Strong alignment with configured titles, skills, industry, and preferences.'
        when match_score >= 60 then 'Partial alignment with the current user configuration.'
        else 'Lower-priority match under the current user configuration.'
    end as reasoning_summary
from weighted
