select *
from {{ ref('mart_jobs_scored') }}
where match_score >= 80
order by match_score desc, salary_midpoint desc nulls last
