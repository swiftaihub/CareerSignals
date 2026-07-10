"""Raw job normalization."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.config.schemas import JobCategoryConfig, NormalizedJob
from src.processing.location_normalization import normalize_location
from src.processing.salary_parser import parse_salary
from src.utils.hashing import stable_hash
from src.utils.text_cleaning import clean_text, normalize_title


def normalize_raw_job(
    raw_job: dict[str, Any],
    category_config: JobCategoryConfig,
    date_collected: str | None = None,
) -> dict[str, Any]:
    """Normalize a raw source record into the CareerSignal job schema."""

    source = clean_text(raw_job.get("source") or "unknown")
    job_title = clean_text(raw_job.get("job_title") or raw_job.get("title"))
    company = clean_text(raw_job.get("company") or raw_job.get("company_name"))
    location = clean_text(raw_job.get("location") or raw_job.get("job_location") or "Unknown")
    location_result = normalize_location(location)
    jd_post_link = clean_text(raw_job.get("jd_post_link") or raw_job.get("url") or "")
    apply_link = clean_text(raw_job.get("apply_link") or raw_job.get("application_url")) or None
    description = clean_text(raw_job.get("job_description") or raw_job.get("description"))
    salary_text = clean_text(
        raw_job.get("salary")
        or raw_job.get("salary_text")
        or raw_job.get("salary_range")
        or raw_job.get("compensation")
    )
    salary_result = parse_salary(f"{salary_text} {description}")

    job_id = stable_hash(source, company, job_title, location, jd_post_link)

    normalized = NormalizedJob(
        job_id=job_id,
        source=source,
        category_name=category_config.category_name,
        job_title=job_title,
        normalized_title=normalize_title(job_title),
        company=company,
        industry=clean_text(raw_job.get("industry") or "Unknown") or "Unknown",
        location=location,
        location_normalized=location_result.normalized,
        location_group=location_result.group,
        work_arrangement=clean_text(raw_job.get("work_arrangement") or "Unknown") or "Unknown",
        employment_type=clean_text(raw_job.get("employment_type") or "full-time") or "full-time",
        seniority=clean_text(raw_job.get("seniority") or "Unknown") or "Unknown",
        salary_min=salary_result.salary_min,
        salary_max=salary_result.salary_max,
        salary_midpoint=salary_result.salary_midpoint,
        salary_range_text=salary_result.salary_range_text,
        date_posted=clean_text(raw_job.get("date_posted")) or None,
        date_collected=date_collected or datetime.now().date().isoformat(),
        jd_post_link=jd_post_link,
        apply_link=apply_link,
        job_description=description,
    )
    return normalized.to_dict()
