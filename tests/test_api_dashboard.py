from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from apps.api.main import app, get_repository
from packages.careersignal_core.repositories.jobs import (
    JobFilters,
    JobRepository,
    PaginatedJobs,
    PipelineQuotaExceededError,
    _apply_derived_fields,
    _apply_local_filters,
    _records,
    get_pipeline_quota,
    reserve_pipeline_run,
)
from src.processing.location_normalization import build_location_facets


JOBS = [
    {
        "job_id": "job-1",
        "job_title": "Senior Analytics Engineer",
        "company": "Alpha Data",
        "category_name": "Analytics Engineer",
        "industry": "SaaS",
        "location": "Remote",
        "work_arrangement": "Remote",
        "visa_signal": "Positive",
        "match_score": 92,
        "match_tier": "Excellent Match",
        "salary_midpoint": 150000,
        "required_skills": ["Python", "SQL", "dbt"],
        "preferred_skills": ["Spark"],
        "all_extracted_skills": ["Python", "SQL", "dbt", "Spark"],
        "reasoning_summary": "Strong data-product fit.",
        "application_status": "Not Applied",
        "date_posted": "2026-07-08",
    },
    {
        "job_id": "job-2",
        "job_title": "BI Analyst",
        "company": "Beta Bank",
        "category_name": "BI Analyst - Banking",
        "industry": "Banking",
        "location": "Philadelphia, PA",
        "work_arrangement": "Hybrid",
        "visa_signal": "Unknown",
        "match_score": 78,
        "match_tier": "Good Match",
        "salary_midpoint": 118000,
        "required_skills": ["SQL", "Power BI"],
        "preferred_skills": [],
        "all_extracted_skills": ["SQL", "Power BI"],
        "reasoning_summary": "Banking analytics role.",
        "application_status": "Saved",
        "date_posted": "2026-06-30",
    },
]


class FakeRepository(JobRepository):
    def __init__(self) -> None:
        self.jobs = list(JOBS)
        self.last_filters: JobFilters | None = None

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        self.last_filters = filters
        filtered = _apply_local_filters(self.jobs, filters)
        return PaginatedJobs(
            total=len(filtered),
            items=filtered[filters.resolved_offset : filters.resolved_offset + filters.resolved_limit],
            page=filters.resolved_page,
            page_size=filters.resolved_page_size,
            limit=filters.resolved_limit,
            offset=filters.resolved_offset,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        job = next((job for job in self.jobs if job["job_id"] == job_id), None)
        return _apply_derived_fields(dict(job)) if job else None

    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str = "personal_user",
    ) -> dict[str, Any]:
        if not self.get_job(job_id):
            raise KeyError(job_id)
        return {
            "job_id": job_id,
            "application_status": application_status,
            "notes": notes,
            "updated_at": "2026-07-08T12:00:00Z",
        }

    def get_filter_options(self) -> dict[str, list[str]]:
        return {
            "categories": sorted({job["category_name"] for job in self.jobs}),
            "companies": sorted({job["company"] for job in self.jobs}),
            "industries": sorted({job["industry"] for job in self.jobs}),
            "locations": sorted({job["location"] for job in self.jobs}),
        }

    def get_facets(self) -> dict[str, Any]:
        return build_location_facets(job["location"] for job in self.jobs)

    def get_top_matches(self) -> list[dict[str, Any]]:
        return [job for job in self.jobs if job["match_score"] >= 80]

    def get_category_summary(self) -> list[dict[str, Any]]:
        return [{"category_name": "Analytics Engineer", "jobs_found": 1}]

    def get_skill_gap(self) -> list[dict[str, Any]]:
        return [{"skill": "dbt", "gap_priority": "Low"}]

    def get_company_priority(self) -> list[dict[str, Any]]:
        return [{"company": "Alpha Data", "priority": "High"}]

    def get_status(self) -> dict[str, Any]:
        return {
            "data_mode": "local",
            "database": "Local",
            "mart_tables_available": False,
            "excel_exists": True,
        }


def test_health_aliases() -> None:
    client = TestClient(app)

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/health").json() == {"status": "ok"}


def test_jobs_endpoint_supports_filtering_sorting_and_pagination() -> None:
    repository = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app)

    response = client.get(
        "/api/jobs",
        params={
            "page": 1,
            "page_size": 1,
            "search": "python",
            "min_match_score": 80,
            "sort_by": "salary_midpoint",
            "sort_order": "desc",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["page"] == 1
    assert payload["page_size"] == 1
    assert payload["items"][0]["job_id"] == "job-1"
    assert repository.last_filters is not None
    assert repository.last_filters.search == "python"


def test_jobs_endpoint_supports_posted_date_filtering() -> None:
    repository = FakeRepository()
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app)

    response = client.get(
        "/api/jobs",
        params={
            "posted_start_date": "2026-07-01",
            "posted_end_date": "2026-07-09",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["job_id"] == "job-1"


def test_jobs_endpoint_rejects_invalid_posted_date_range() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    response = client.get(
        "/api/jobs",
        params={
            "posted_start_date": "2026-07-10",
            "posted_end_date": "2026-07-09",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "INVALID_POSTED_DATE_RANGE"


def test_job_filter_options_endpoint() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    response = client.get("/api/jobs/filter-options")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["companies"] == ["Alpha Data", "Beta Bank"]


def test_job_facets_endpoint_returns_grouped_location_metadata() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    response = client.get("/api/jobs/facets")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert {"group": "Remote", "value": "Remote", "count": 1} in payload["locations"]
    assert {"group": "Northeast", "value": "Philadelphia, PA", "count": 1} in payload["locations"]
    assert {"group": "Northeast", "count": 1} in payload["location_groups"]


def test_jobs_endpoint_supports_location_group_and_free_text_filters() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    by_group = client.get("/api/jobs", params={"location_group": "Northeast"})
    by_text = client.get("/api/jobs", params={"location": "PA"})

    app.dependency_overrides.clear()

    assert by_group.status_code == 200
    assert by_group.json()["total"] == 1
    assert by_group.json()["items"][0]["job_id"] == "job-2"
    assert by_text.status_code == 200
    assert by_text.json()["total"] == 1
    assert by_text.json()["items"][0]["location_group"] == "Northeast"


def test_job_detail_and_status_update() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    detail = client.get("/api/jobs/job-1")
    status = client.patch(
        "/api/jobs/job-1/status",
        json={
            "application_status": "Applied",
            "notes": "Applied through company career page.",
        },
    )
    missing = client.get("/api/jobs/unknown")

    app.dependency_overrides.clear()

    assert detail.status_code == 200
    assert detail.json()["company"] == "Alpha Data"
    assert status.status_code == 200
    assert status.json()["application_status"] == "Applied"
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "JOB_NOT_FOUND"


def test_dashboard_summary_endpoint() -> None:
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    client = TestClient(app)

    response = client.get("/api/dashboard/summary")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["metrics"]["total_jobs"] == 2
    assert payload["metrics"]["top_matches"] == 1
    assert payload["data_status"]["data_mode"] == "local"


def test_local_filtering_logic() -> None:
    filtered = _apply_local_filters(
        JOBS,
        JobFilters(
            company="alpha",
            min_match_score=90,
            search="dbt",
            sort_by="salary_midpoint",
            sort_order="desc",
        ),
    )

    assert [job["job_id"] for job in filtered] == ["job-1"]


def test_legacy_visa_signal_gets_descriptive_status_fallback() -> None:
    record = _apply_derived_fields({"job_id": "legacy-negative", "visa_signal": "Negative"})

    assert record["visa_status"] == "No Sponsorship"
    assert record["visa_confidence"] == "Low"


def test_records_convert_pandas_missing_scalars_to_json_none() -> None:
    rows = _records(
        pd.DataFrame(
            [
                {
                    "Job ID": "job-missing",
                    "Match Score": 92.0,
                    "notes": float("nan"),
                    "application_updated_at": pd.NaT,
                }
            ]
        )
    )

    assert rows[0]["notes"] is None
    assert rows[0]["application_updated_at"] is None


def test_pipeline_quota_allows_two_runs_per_window(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CAREERSIGNAL_OUTPUT_DIR", str(tmp_path))

    reserve_pipeline_run("pipeline-test-1")
    reserve_pipeline_run("pipeline-test-2")
    quota = get_pipeline_quota()

    assert quota["limit"] == 2
    assert quota["remaining"] == 0
    with pytest.raises(PipelineQuotaExceededError):
        reserve_pipeline_run("pipeline-test-3")


def test_pipeline_quota_window_resets_at_6am_eastern(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CAREERSIGNAL_OUTPUT_DIR", str(tmp_path))
    eastern = ZoneInfo("America/New_York")

    before_reset = get_pipeline_quota(datetime(2026, 7, 9, 5, 59, tzinfo=eastern))
    after_reset = get_pipeline_quota(datetime(2026, 7, 9, 6, 0, tzinfo=eastern))

    assert before_reset["window_start"].startswith("2026-07-08T06:00:00")
    assert before_reset["window_end"].startswith("2026-07-09T06:00:00")
    assert after_reset["window_start"].startswith("2026-07-09T06:00:00")
    assert after_reset["window_end"].startswith("2026-07-10T06:00:00")
