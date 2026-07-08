select
    skill,
    skill_group,
    in_candidate_profile
from {{ source('staging', 'python_candidate_skills') }}
where skill is not null
