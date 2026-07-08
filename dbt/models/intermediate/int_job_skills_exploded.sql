with exploded as (
    select
        jobs.job_id,
        jobs.job_title,
        trim(both '"' from cast(skills.value as varchar)) as skill
    from {{ ref('int_job_posts_deduped') }} as jobs,
    json_each(cast(coalesce(nullif(jobs.all_extracted_skills, ''), '[]') as json)) as skills
),

cleaned as (
    select
        job_id,
        job_title,
        trim(skill) as skill
    from exploded
    where trim(skill) <> ''
)

select
    cleaned.job_id,
    cleaned.job_title,
    cleaned.skill,
    coalesce(candidate.skill_group, 'Market Skill') as skill_group,
    coalesce(candidate.in_candidate_profile, false) as in_candidate_profile
from cleaned
left join {{ ref('stg_candidate_skills') }} as candidate
    on lower(cleaned.skill) = lower(candidate.skill)
