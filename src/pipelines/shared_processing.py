"""Candidate-independent processing for the shared Connector job universe."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from src.config.schemas import FreshnessFilter, JobCategoryConfig, VisaKeywords
from src.processing.date_filter import freshness_decision
from src.processing.industry_classifier import classify_industry
from src.processing.normalize import normalize_raw_job
from src.processing.seniority_classifier import classify_seniority
from src.processing.visa_signal import classify_visa_signal
from src.processing.work_arrangement import detect_work_arrangement
from src.utils.progress import ProgressReporter

LOGGER = logging.getLogger(__name__)


def normalize_shared_jobs(
    raw_records: list[dict[str, Any]],
    progress: ProgressReporter | None = None,
) -> list[dict[str, Any]]:
    iterable: Iterable[dict[str, Any]] = (
        progress.iter(raw_records, "Normalizing shared jobs", total=len(raw_records))
        if progress
        else raw_records
    )
    normalized: list[dict[str, Any]] = []
    for record in iterable:
        category = record.get("_careersignal_category")
        if not isinstance(category, JobCategoryConfig):
            raise ValueError("shared raw record is missing its platform acquisition category")
        normalized.append(normalize_raw_job(record, category))
    return normalized


def apply_shared_freshness_filter(
    raw_records: list[dict[str, Any]],
    normalized_jobs: list[dict[str, Any]],
    freshness_filter: FreshnessFilter,
    progress: ProgressReporter | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    stats = {
        "input_jobs": len(normalized_jobs),
        "kept_jobs": 0,
        "older_than_max_age": 0,
        "unknown_date_excluded": 0,
        "unknown_date_included": 0,
        "disabled": 0,
    }
    if not freshness_filter.enabled:
        stats["kept_jobs"] = len(normalized_jobs)
        stats["disabled"] = len(normalized_jobs)
        return raw_records, normalized_jobs, stats

    pairs = list(zip(raw_records, normalized_jobs))
    iterable = (
        progress.iter(pairs, "Applying shared freshness policy", total=len(pairs))
        if progress
        else pairs
    )
    kept_raw: list[dict[str, Any]] = []
    kept_jobs: list[dict[str, Any]] = []
    for raw_record, job in iterable:
        decision = freshness_decision(job, freshness_filter)
        stats[decision.reason] = stats.get(decision.reason, 0) + 1
        if decision.keep:
            kept_raw.append(raw_record)
            kept_jobs.append(job)
    stats["kept_jobs"] = len(kept_jobs)
    return kept_raw, kept_jobs, stats


def enrich_shared_jobs(
    jobs: list[dict[str, Any]],
    progress: ProgressReporter | None = None,
) -> list[dict[str, Any]]:
    """Apply only candidate-independent classifications.

    Skill extraction and match scoring intentionally occur in the user dbt
    selector because both depend on a user's immutable configuration snapshot.
    """

    iterable = (
        progress.iter(jobs, "Enriching shared jobs", total=len(jobs))
        if progress
        else jobs
    )
    enriched_jobs: list[dict[str, Any]] = []
    for job in iterable:
        description = str(job.get("job_description") or "")
        category = JobCategoryConfig(
            category_name=str(job.get("category_name") or "Shared"),
            search_titles=[],
            industries=[],
            seniority=[],
        )
        visa = classify_visa_signal(description, VisaKeywords())
        enriched_jobs.append(
            {
                **job,
                "industry": classify_industry(
                    category,
                    str(job.get("company") or ""),
                    description,
                    str(job.get("industry") or ""),
                ),
                "seniority": classify_seniority(
                    str(job.get("job_title") or ""), description
                ),
                "work_arrangement": detect_work_arrangement(
                    str(job.get("job_title") or ""),
                    str(job.get("location") or ""),
                    description,
                ),
                "visa_signal": visa.visa_signal,
                "visa_status": visa.visa_status,
                "visa_evidence": visa.visa_evidence,
                "visa_confidence": visa.visa_confidence,
                "required_skills": [],
                "preferred_skills": [],
                "all_extracted_skills": [],
                "match_score": 0.0,
                "match_tier": "Unscored",
                "reasoning_summary": "",
            }
        )
    return enriched_jobs
