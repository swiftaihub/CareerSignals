from __future__ import annotations

from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Any
from uuid import UUID

import pytest

from apps.api.dependencies.models import CurrentUser
from apps.api.dependencies import repositories as repository_dependencies
from packages.careersignal_core.repositories.dashboard_analytics import (
    DashboardAnalyticsResult,
    DashboardFunnelMetrics,
    JobCountTimeseriesPoint,
)
from packages.careersignal_core.repositories.jobs import PostgresJobRepository


USER_UUID = "11111111-1111-4111-8111-111111111111"


class _Cursor:
    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self.row = row

    def fetchone(self) -> dict[str, Any] | None:
        return self.row


class _StatusConnection:
    def __init__(self, *, owns_job: bool = True) -> None:
        self.owns_job = owns_job
        self.statements: list[tuple[str, list[Any]]] = []

    def execute(self, statement: str, params: list[Any] | None = None) -> _Cursor:
        normalized = " ".join(statement.casefold().split())
        values = list(params or [])
        self.statements.append((normalized, values))
        if "select 1 from public.user_job_matches" in normalized:
            return _Cursor({"owned": 1} if self.owns_job else None)
        if "insert into public.user_job_statuses" in normalized:
            return _Cursor(
                {
                    "job_id": values[1],
                    "application_status": "Interview",
                    "notes": values[3],
                    "updated_at": "2026-07-12T12:00:00Z",
                }
            )
        return _Cursor()


class _Transaction(AbstractContextManager[_StatusConnection]):
    def __init__(self, connection: _StatusConnection) -> None:
        self.connection = connection

    def __enter__(self) -> _StatusConnection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        return None


class _StatusStore:
    def __init__(self, *, owns_job: bool = True) -> None:
        self.connection = _StatusConnection(owns_job=owns_job)

    def transaction(self) -> _Transaction:
        return _Transaction(self.connection)


def test_postgres_status_update_is_tenant_scoped_and_triggered_in_one_transaction() -> None:
    store = _StatusStore()
    repository = PostgresJobRepository(USER_UUID, store=store)  # type: ignore[arg-type]

    result = repository.update_job_status("job-1", "Interview", "Recruiter screen")

    statements = store.connection.statements
    assert result["application_status"] == "Interview"
    assert len(statements) == 2
    assert statements[0][1] == [USER_UUID, "job-1"]
    assert statements[1][1] == [USER_UUID, "job-1", "interview", "Recruiter screen"]


def test_postgres_status_update_rejects_a_job_outside_current_user_partition() -> None:
    store = _StatusStore(owns_job=False)
    repository = PostgresJobRepository(USER_UUID, store=store)  # type: ignore[arg-type]

    with pytest.raises(KeyError):
        repository.update_job_status("foreign-job", "Applied")

    assert len(store.connection.statements) == 1
    assert store.connection.statements[0][1] == [USER_UUID, "foreign-job"]


class _SummaryStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    def fetch_one(self, statement: str, params: list[Any] | None = None) -> dict[str, Any]:
        normalized = " ".join(statement.casefold().split())
        values = list(params or [])
        self.calls.append((normalized, values))
        if "count(distinct matches.job_id)" in normalized:
            return {
                "total_jobs": 6400,
                "top_matches": 625,
                "average_match_score": 82.4,
                "average_salary_midpoint": 145000,
                "remote_or_hybrid_roles": 4100,
                "positive_or_unknown_visa_roles": 5200,
            }
        return {
            "status": "completed",
            "completed_at": None,
            "published_at": None,
            "jobs_matched": 6400,
        }

    def fetch_all(self, statement: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        normalized = " ".join(statement.casefold().split())
        values = list(params or [])
        self.calls.append((normalized, values))
        if "from dimensions" in normalized:
            return [
                {"dimension": "visa_signal", "label": "Positive", "count": 10},
                {"dimension": "work_arrangement", "label": "Remote", "count": 8},
                {"dimension": "match_tier", "label": "Strong Match", "count": 6},
            ]
        if "from public.user_category_summary" in normalized:
            return []
        return [
            {
                "job_id": "job-top",
                "job_title": "Analytics Lead",
                "match_score": 97,
                "application_status": "Not Applied",
            }
        ]


class _Analytics:
    def get_analytics(self, **kwargs: Any) -> DashboardAnalyticsResult:
        assert kwargs == {"user_uuid": USER_UUID, "days": 30, "is_demo": True}
        return DashboardAnalyticsResult(
            funnel=DashboardFunnelMetrics(6400, 6400, 12, 3),
            job_count_timeseries=[
                JobCountTimeseriesPoint(date(2026, 7, 12), 6400, 6400, 12)
            ],
            start_date=date(2026, 6, 13),
            end_date=date(2026, 7, 12),
            days=30,
        )


def test_postgres_dashboard_uses_aggregate_queries_and_preserves_demo_scope() -> None:
    store = _SummaryStore()
    repository = PostgresJobRepository(
        USER_UUID,
        store=store,  # type: ignore[arg-type]
        is_demo=True,
    )
    repository.dashboard_analytics = _Analytics()  # type: ignore[assignment]

    summary = repository.get_dashboard_summary(days=30)

    assert summary["metrics"]["total_jobs"] == 6400
    assert summary["funnel"]["total_global_jobs"] == 6400
    assert summary["top_matches_preview"][0]["job_id"] == "job-top"
    aggregate_sql, aggregate_params = store.calls[0]
    assert "limit 5000" not in aggregate_sql
    assert "'nan', 'infinity', '-infinity'" in aggregate_sql
    assert aggregate_params == [80, USER_UUID]
    assert all(
        USER_UUID in params
        for sql, params in store.calls
        if "user_" in sql or "matches.user_uuid" in sql
    )


def test_repository_dependency_passes_verified_demo_role(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def build(user_uuid: str, *, is_demo: bool = False) -> object:
        captured.update(user_uuid=user_uuid, is_demo=is_demo)
        return object()

    monkeypatch.setattr(repository_dependencies, "build_job_repository", build)
    current_user = CurrentUser(
        user_uuid=UUID(USER_UUID),
        username="demo",
        role="demo",
        account_status="active",
        created_at=datetime(2026, 7, 12),
        activated_at=None,
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )

    repository_dependencies.get_repository(current_user)

    assert captured == {"user_uuid": USER_UUID, "is_demo": True}
