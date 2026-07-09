"""FastAPI application for CareerSignal dashboard data."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # pragma: no cover
    pass

from packages.careersignal_core.dbt.runner import run_dbt, test_dbt
from packages.careersignal_core.repositories.jobs import (
    APPLICATION_STATUSES,
    JobFilters,
    JobRepository,
    PaginatedJobs,
    build_job_repository,
    write_operation_state,
)
from packages.careersignal_core.settings import dbt_profiles_dir, dbt_project_dir
from packages.careersignal_core.storage.motherduck import MotherDuckConfigurationError
from src.main import export_excel_from_current_data, run_pipeline


def _cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


app = FastAPI(title="CareerSignal API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobStatusUpdate(BaseModel):
    application_status: str = Field(..., min_length=1)
    notes: str | None = Field(default=None, max_length=4000)


def get_repository() -> JobRepository:
    return build_job_repository()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _api_error(status_code: int, detail: str, error_code: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"detail": detail, "error_code": error_code},
    )


def _paginated_response(page: PaginatedJobs) -> dict[str, Any]:
    return {
        "items": page.items,
        "total": page.total,
        "page": page.page,
        "page_size": page.page_size,
        "limit": page.limit,
        "offset": page.offset,
    }


@app.exception_handler(MotherDuckConfigurationError)
def motherduck_configuration_handler(_, exc: MotherDuckConfigurationError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "MotherDuck mode is enabled but not fully configured.",
            "error_code": "MOTHERDUCK_CONFIGURATION_ERROR",
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def root_health() -> dict[str, str]:
    return health()


@app.get("/api/jobs")
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
    work_arrangement: str | None = None,
    visa_signal: str | None = None,
    application_status: str | None = None,
    search: str | None = None,
    sort_by: str = Query(default="match_score"),
    sort_order: str = Query(default="desc"),
    repository: JobRepository = Depends(get_repository),
):
    jobs_page = repository.get_jobs(
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
            work_arrangement=work_arrangement,
            visa_signal=visa_signal,
            application_status=application_status,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )
    return _paginated_response(jobs_page)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, repository: JobRepository = Depends(get_repository)):
    job = repository.get_job(job_id)
    if not job:
        raise _api_error(404, "Job was not found.", "JOB_NOT_FOUND")
    return job


@app.patch("/api/jobs/{job_id}/status")
def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    repository: JobRepository = Depends(get_repository),
):
    if payload.application_status not in APPLICATION_STATUSES:
        raise _api_error(400, "Application status is not supported.", "INVALID_APPLICATION_STATUS")
    try:
        return repository.update_job_status(
            job_id=job_id,
            application_status=payload.application_status,
            notes=payload.notes,
        )
    except KeyError:
        raise _api_error(404, "Job was not found.", "JOB_NOT_FOUND") from None
    except ValueError as exc:
        raise _api_error(400, str(exc), "INVALID_APPLICATION_STATUS") from exc


@app.get("/api/top-matches")
def get_top_matches(repository: JobRepository = Depends(get_repository)):
    return repository.get_top_matches()


@app.get("/api/category-summary")
def get_category_summary(repository: JobRepository = Depends(get_repository)):
    return repository.get_category_summary()


@app.get("/api/skill-gap")
def get_skill_gap(repository: JobRepository = Depends(get_repository)):
    return repository.get_skill_gap()


@app.get("/api/company-priority")
def get_company_priority(repository: JobRepository = Depends(get_repository)):
    return repository.get_company_priority()


@app.get("/api/data/status")
def get_data_status(repository: JobRepository = Depends(get_repository)):
    return repository.get_status()


@app.get("/api/dashboard/summary")
def get_dashboard_summary(repository: JobRepository = Depends(get_repository)):
    return repository.get_dashboard_summary()


@app.post("/api/pipeline/run")
def run_pipeline_endpoint():
    summary = run_pipeline(ROOT)
    write_operation_state(
        last_pipeline_run_at=_now_iso(),
        excel_path=str(summary.get("output_path")) if summary.get("output_path") else None,
    )
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in summary.items()
        if key != "jobs"
    }


@app.post("/api/excel/export")
def export_excel_endpoint():
    output_path = export_excel_from_current_data(ROOT)
    write_operation_state(last_excel_export_at=_now_iso(), excel_path=str(output_path))
    return {"status": "completed", "output_path": str(output_path)}


@app.get("/api/excel/download")
def download_excel_endpoint(repository: JobRepository = Depends(get_repository)):
    status = repository.get_status()
    excel_path = status.get("excel_path")
    if not excel_path:
        raise _api_error(404, "No Excel workbook is available yet.", "EXCEL_NOT_AVAILABLE")

    workbook_path = Path(str(excel_path))
    if not workbook_path.is_absolute():
        workbook_path = ROOT / workbook_path
    if not workbook_path.exists():
        raise _api_error(404, "Excel workbook file was not found.", "EXCEL_NOT_FOUND")

    return FileResponse(
        workbook_path,
        filename=workbook_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/dbt/run")
def run_dbt_endpoint(full_refresh: bool = Query(default=False)):
    run_dbt(dbt_project_dir(), dbt_profiles_dir(), full_refresh=full_refresh)
    write_operation_state(last_dbt_run_at=_now_iso())
    return {"status": "completed"}


@app.post("/api/dbt/test")
def test_dbt_endpoint():
    test_dbt(dbt_project_dir(), dbt_profiles_dir())
    write_operation_state(last_dbt_test_at=_now_iso())
    return {"status": "completed"}
