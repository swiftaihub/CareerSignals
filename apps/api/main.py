"""FastAPI application for CareerSignal dashboard data."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
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
    PipelineQuotaExceededError,
    append_pipeline_run_message,
    build_job_repository,
    complete_pipeline_run_state,
    fail_pipeline_run_state,
    get_pipeline_quota,
    get_pipeline_run_state,
    reserve_pipeline_run,
    write_operation_state,
)
from packages.careersignal_core.settings import dbt_profiles_dir, dbt_project_dir
from packages.careersignal_core.storage.motherduck import MotherDuckConfigurationError
from src.main import export_excel_from_current_data, run_pipeline

LOGGER = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    for local_origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        if local_origin not in origins:
            origins.append(local_origin)
    return origins


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


def _serialize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in summary.items()
        if key != "jobs"
    }


def _new_pipeline_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"pipeline_{stamp}_{uuid4().hex[:8]}"


class _PipelineLogHandler(logging.Handler):
    def __init__(self, run_id: str) -> None:
        super().__init__(level=logging.INFO)
        self.run_id = run_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = "error" if record.levelno >= logging.ERROR else "warning" if record.levelno >= logging.WARNING else "info"
            append_pipeline_run_message(self.run_id, self.format(record), level=level)
        except Exception:
            pass


def _execute_pipeline_run(run_id: str) -> None:
    append_pipeline_run_message(run_id, "Loading configuration and job sources")
    handler = _PipelineLogHandler(run_id)
    handler.setFormatter(logging.Formatter("%(message)s"))
    loggers = [
        logging.getLogger("src"),
        logging.getLogger("packages.careersignal_core"),
    ]
    previous_levels = {logger: logger.level for logger in loggers}
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    try:
        summary = run_pipeline(ROOT)
        serialized_summary = _serialize_summary(summary)
        write_operation_state(
            last_pipeline_run_at=_now_iso(),
            excel_path=str(summary.get("output_path")) if summary.get("output_path") else None,
        )
        complete_pipeline_run_state(run_id, serialized_summary)
    except Exception as exc:
        LOGGER.exception("Pipeline run %s failed.", run_id)
        fail_pipeline_run_state(run_id, f"Pipeline failed: {exc}")
    finally:
        for logger in loggers:
            logger.removeHandler(handler)
            logger.setLevel(previous_levels[logger])


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
    posted_start_date: date | None = Query(default=None),
    posted_end_date: date | None = Query(default=None),
    sort_by: str = Query(default="match_score"),
    sort_order: str = Query(default="desc"),
    repository: JobRepository = Depends(get_repository),
):
    if posted_start_date and posted_end_date and posted_start_date > posted_end_date:
        raise _api_error(
            400,
            "Posted From must be on or before Posted To.",
            "INVALID_POSTED_DATE_RANGE",
        )
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
            posted_start_date=posted_start_date,
            posted_end_date=posted_end_date,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )
    return _paginated_response(jobs_page)


@app.get("/api/jobs/filter-options")
def get_job_filter_options(repository: JobRepository = Depends(get_repository)):
    return repository.get_filter_options()


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


@app.post("/api/pipeline/run", status_code=202)
def run_pipeline_endpoint(background_tasks: BackgroundTasks):
    run_id = _new_pipeline_run_id()
    try:
        run_record = reserve_pipeline_run(run_id)
    except PipelineQuotaExceededError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "Daily pipeline refresh limit reached. Refreshes reset at 6:00 AM ET.",
                "error_code": "PIPELINE_QUOTA_EXCEEDED",
                "resets_at": exc.quota["resets_at"],
            },
        ) from exc

    background_tasks.add_task(_execute_pipeline_run, run_id)
    return {**run_record, "quota": get_pipeline_quota()}


@app.get("/api/pipeline/runs/{run_id}")
def get_pipeline_run(run_id: str):
    run_record = get_pipeline_run_state(run_id)
    if not run_record:
        raise _api_error(404, "Pipeline run was not found.", "PIPELINE_RUN_NOT_FOUND")
    return {**run_record, "quota": get_pipeline_quota()}


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
