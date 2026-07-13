from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies.authorization import CurrentUser, require_non_demo_user
from apps.api.dependencies.repositories import get_repository
from apps.api.schemas.jobs import DashboardSummary, JobStatusUpdate
from packages.careersignal_core.repositories.jobs import (
    APPLICATION_STATUSES,
    JobFilters,
    JobRepository,
    PaginatedJobs,
)

router = APIRouter(prefix="/api", tags=["jobs"])


def _api_error(status_code: int, detail: str, error_code: str) -> HTTPException:
    # Keep the legacy nested error shape for existing clients during migration.
    return HTTPException(status_code=status_code, detail={"detail": detail, "error_code": error_code})


def _paginated_response(page: PaginatedJobs) -> dict[str, Any]:
    return {
        "items": page.items,
        "total": page.total,
        "page": page.page,
        "page_size": page.page_size,
        "limit": page.limit,
        "offset": page.offset,
    }


@router.get("/jobs")
def get_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    category_name: str | None = None,
    min_match_score: float | None = Query(default=None, ge=0, le=100),
    max_match_score: float | None = Query(default=None, ge=0, le=100),
    company: str | None = None,
    industry: str | None = None,
    location: str | None = None,
    location_group: str | None = None,
    work_arrangement: str | None = None,
    visa_signal: str | None = None,
    application_status: str | None = None,
    search: str | None = None,
    posted_start_date: date | None = Query(default=None),
    posted_end_date: date | None = Query(default=None),
    sort_by: str = Query(default="match_score"),
    sort_order: str = Query(default="desc"),
    repository: JobRepository = Depends(get_repository),
) -> dict[str, Any]:
    if posted_start_date and posted_end_date and posted_start_date > posted_end_date:
        raise _api_error(400, "Posted From must be on or before Posted To.", "INVALID_POSTED_DATE_RANGE")
    return _paginated_response(
        repository.get_jobs(
            JobFilters(
                limit=limit,
                offset=offset,
                page=page,
                page_size=page_size,
                category_name=category_name,
                min_match_score=min_match_score,
                max_match_score=max_match_score,
                company=company,
                industry=industry,
                location=location,
                location_group=location_group,
                work_arrangement=work_arrangement,
                visa_signal=visa_signal,
                application_status=application_status,
                search=search,
                posted_start_date=posted_start_date,
                posted_end_date=posted_end_date,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )
    )


@router.get("/jobs/filter-options")
def get_job_filter_options(repository: JobRepository = Depends(get_repository)) -> dict[str, list[str]]:
    return repository.get_filter_options()


@router.get("/jobs/facets")
def get_job_facets(repository: JobRepository = Depends(get_repository)) -> dict[str, Any]:
    return repository.get_facets()


@router.get("/jobs/{job_id}")
def get_job(job_id: str, repository: JobRepository = Depends(get_repository)) -> dict[str, Any]:
    job = repository.get_job(job_id)
    if not job:
        raise _api_error(404, "Job was not found.", "JOB_NOT_FOUND")
    return job


@router.patch("/jobs/{job_id}/status")
def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    repository: JobRepository = Depends(get_repository),
    _: CurrentUser = Depends(require_non_demo_user),
) -> dict[str, Any]:
    if payload.application_status not in APPLICATION_STATUSES:
        raise _api_error(400, "Application status is not supported.", "INVALID_APPLICATION_STATUS")
    try:
        return repository.update_job_status(job_id, payload.application_status, payload.notes)
    except KeyError:
        raise _api_error(404, "Job was not found.", "JOB_NOT_FOUND") from None
    except ValueError as exc:
        raise _api_error(400, str(exc), "INVALID_APPLICATION_STATUS") from exc


@router.get("/top-matches")
def get_top_matches(repository: JobRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.get_top_matches()


@router.get("/category-summary")
def get_category_summary(repository: JobRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.get_category_summary()


@router.get("/skill-gap")
def get_skill_gap(repository: JobRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.get_skill_gap()


@router.get("/company-priority")
def get_company_priority(repository: JobRepository = Depends(get_repository)) -> list[dict[str, Any]]:
    return repository.get_company_priority()


@router.get("/data/status")
def get_data_status(repository: JobRepository = Depends(get_repository)) -> dict[str, Any]:
    return repository.get_status()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    days: int = Query(default=30, ge=7, le=365),
    repository: JobRepository = Depends(get_repository),
) -> DashboardSummary:
    return DashboardSummary.model_validate(repository.get_dashboard_summary(days=days))
