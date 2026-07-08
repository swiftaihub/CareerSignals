select
    jobs.job_id,
    jobs.category_name,
    jobs.match_tier,
    jobs.match_score,
    jobs.job_title,
    jobs.normalized_title,
    jobs.company,
    jobs.industry,
    jobs.location,
    jobs.work_arrangement,
    jobs.seniority,
    jobs.employment_type,
    jobs.salary_range_text,
    jobs.salary_min,
    jobs.salary_max,
    jobs.salary_midpoint,
    jobs.visa_signal,
    jobs.required_skills,
    jobs.preferred_skills,
    jobs.all_extracted_skills,
    jobs.jd_post_link,
    jobs.apply_link,
    jobs.date_posted,
    jobs.date_collected,
    jobs.source,
    coalesce(status.application_status, 'Not Applied') as application_status,
    jobs.reasoning_summary,
    jobs.run_id,
    jobs.inserted_at
from {{ ref('int_job_posts_deduped') }} as jobs
left join {{ ref('int_latest_job_status') }} as status
    on jobs.job_id = status.job_id
    and status.user_id = 'personal_user'
