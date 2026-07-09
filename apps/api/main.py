"""FastAPI application for CareerSignal dashboard data."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
    JobFilters,
    JobRepository,
    build_job_repository,
)
from packages.careersignal_core.settings import dbt_profiles_dir, dbt_project_dir
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


def get_repository() -> JobRepository:
    return build_job_repository()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/jobs")
def get_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category_name: str | None = None,
    min_match_score: float | None = Query(default=None, ge=0, le=100),
    repository: JobRepository = Depends(get_repository),
):
    return repository.get_jobs(
        JobFilters(
            limit=limit,
            offset=offset,
            category_name=category_name,
            min_match_score=min_match_score,
        )
    )


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


@app.post("/api/pipeline/run")
def run_pipeline_endpoint():
    summary = run_pipeline(ROOT)
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in summary.items()
        if key != "jobs"
    }


@app.post("/api/excel/export")
def export_excel_endpoint():
    output_path = export_excel_from_current_data(ROOT)
    return {"status": "completed", "output_path": str(output_path)}


@app.get("/api/excel/download")
def download_excel_endpoint(repository: JobRepository = Depends(get_repository)):
    status = repository.get_status()
    excel_path = status.get("excel_path")
    if not excel_path:
        raise HTTPException(status_code=404, detail="No Excel workbook is available yet.")

    workbook_path = Path(str(excel_path))
    if not workbook_path.is_absolute():
        workbook_path = ROOT / workbook_path
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail="Excel workbook file was not found.")

    return FileResponse(
        workbook_path,
        filename=workbook_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/dbt/run")
def run_dbt_endpoint(full_refresh: bool = False):
    run_dbt(dbt_project_dir(), dbt_profiles_dir(), full_refresh=full_refresh)
    return {"status": "completed"}


@app.post("/api/dbt/test")
def test_dbt_endpoint():
    test_dbt(dbt_project_dir(), dbt_profiles_dir())
    return {"status": "completed"}
