from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest

from packages.careersignal_core.repositories.dashboard_analytics import (
    DashboardAnalyticsRepository,
    build_daily_timeseries,
)


USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    def execute(self, statement: str, params: list[Any] | None = None) -> None:
        self.calls.append((" ".join(statement.split()), list(params or [])))


class _Store:
    def __init__(self) -> None:
        self.connection = _Connection()
        self.fetch_all_calls: list[tuple[str, list[Any]]] = []
        self.fetch_one_calls: list[tuple[str, list[Any]]] = []
        self.global_rows: list[dict[str, Any]] = []
        self.user_rows: dict[str, list[dict[str, Any]]] = {}
        self.funnels: dict[str, dict[str, Any]] = {}

    @contextmanager
    def transaction(self):
        yield self.connection

    def fetch_all(self, statement: str, params: list[Any]) -> list[dict[str, Any]]:
        normalized = " ".join(statement.split())
        self.fetch_all_calls.append((normalized, list(params)))
        if "global_job_daily_metrics" in normalized:
            return self.global_rows
        return self.user_rows.get(str(params[0]), [])

    def fetch_one(self, statement: str, params: list[Any]) -> dict[str, Any]:
        normalized = " ".join(statement.split())
        self.fetch_one_calls.append((normalized, list(params)))
        return self.funnels.get(str(params[0]), {})


def test_sparse_series_uses_daily_new_counts_and_zero_fills_known_gaps() -> None:
    points = build_daily_timeseries(
        global_rows=[
            {"metric_date": date(2026, 7, 10), "new_global_jobs_count": 10},
            {"metric_date": date(2026, 7, 12), "new_global_jobs_count": 4},
        ],
        user_rows=[
            {
                "metric_date": date(2026, 7, 11),
                "new_user_jobs_count": 3,
                "new_applied_jobs_count": 2,
            }
        ],
        start_date=date(2026, 7, 9),
        end_date=date(2026, 7, 12),
    )

    assert [point.as_dict() for point in points] == [
        {"date": date(2026, 7, 10), "global_jobs": 10, "user_jobs": None, "applied_jobs": None},
        {"date": date(2026, 7, 11), "global_jobs": 0, "user_jobs": 3, "applied_jobs": 2},
        {"date": date(2026, 7, 12), "global_jobs": 4, "user_jobs": 0, "applied_jobs": 0},
    ]


def test_unknown_days_are_omitted_but_known_zero_days_are_retained() -> None:
    unknown = build_daily_timeseries(
        global_rows=[],
        user_rows=[],
        start_date=date(2026, 7, 9),
        end_date=date(2026, 7, 10),
    )
    known_zero = build_daily_timeseries(
        global_rows=[{"metric_date": date(2026, 7, 10), "new_global_jobs_count": 0}],
        user_rows=[],
        start_date=date(2026, 7, 9),
        end_date=date(2026, 7, 10),
    )

    assert unknown == []
    assert [point.as_dict() for point in known_zero] == [
        {
            "date": date(2026, 7, 10),
            "global_jobs": 0,
            "user_jobs": None,
            "applied_jobs": None,
        }
    ]


def test_snapshot_before_window_establishes_zero_filled_history_not_a_total() -> None:
    points = build_daily_timeseries(
        global_rows=[{"metric_date": date(2026, 6, 30), "new_global_jobs_count": 8}],
        user_rows=[
            {
                "metric_date": date(2026, 6, 29),
                "new_user_jobs_count": 7,
                "new_applied_jobs_count": 1,
            }
        ],
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
    )

    assert [(point.global_jobs, point.user_jobs, point.applied_jobs) for point in points] == [
        (0, 0, 0),
        (0, 0, 0),
    ]


def test_demo_series_uses_only_its_fixture_scoped_user_history() -> None:
    points = build_daily_timeseries(
        global_rows=[{"metric_date": date(2026, 7, 12), "new_global_jobs_count": 9999}],
        user_rows=[
            {
                "metric_date": date(2026, 7, 12),
                "new_user_jobs_count": 20,
                "new_applied_jobs_count": 0,
            }
        ],
        start_date=date(2026, 7, 12),
        end_date=date(2026, 7, 12),
        is_demo=True,
    )

    assert points[0].global_jobs == 20
    assert points[0].user_jobs == 20


def test_same_day_snapshot_writes_use_idempotent_database_upserts() -> None:
    store = _Store()
    repository = DashboardAnalyticsRepository(store)  # type: ignore[arg-type]
    snapshot_date = date(2026, 7, 12)

    repository.record_user_snapshot(user_uuid=USER_A, metric_date=snapshot_date)
    repository.record_user_snapshot(user_uuid=USER_A, metric_date=snapshot_date)

    assert len(store.connection.calls) == 2
    assert all("upsert_user_job_daily_metric" in statement for statement, _ in store.connection.calls)
    assert store.connection.calls[0][1] == [USER_A, None, snapshot_date]
    assert store.connection.calls[1][1] == [USER_A, None, snapshot_date]


def test_analytics_reads_are_scoped_to_the_requested_verified_tenant() -> None:
    store = _Store()
    store.funnels = {
        USER_A: {
            "global_jobs_count": 100,
            "user_jobs_count": 3,
            "applied_jobs_count": 2,
            "interview_jobs_count": 1,
        },
        USER_B: {
            "global_jobs_count": 100,
            "user_jobs_count": 8,
            "applied_jobs_count": 4,
            "interview_jobs_count": 2,
        },
    }
    store.user_rows = {
        USER_A: [
            {
                "metric_date": date(2026, 7, 12),
                "new_user_jobs_count": 3,
                "new_applied_jobs_count": 2,
            }
        ],
        USER_B: [
            {
                "metric_date": date(2026, 7, 12),
                "new_user_jobs_count": 8,
                "new_applied_jobs_count": 4,
            }
        ],
    }
    repository = DashboardAnalyticsRepository(store)  # type: ignore[arg-type]

    summary_a = repository.get_analytics(
        user_uuid=USER_A, days=7, end_date=date(2026, 7, 12)
    )
    summary_b = repository.get_analytics(
        user_uuid=USER_B, days=7, end_date=date(2026, 7, 12)
    )

    assert summary_a.funnel.total_user_jobs == 3
    assert summary_b.funnel.total_user_jobs == 8
    assert summary_a.job_count_timeseries[-1].user_jobs == 3
    assert summary_b.job_count_timeseries[-1].user_jobs == 8
    global_query = next(
        statement
        for statement, _ in store.fetch_all_calls
        if "global_job_daily_metrics" in statement
    )
    user_queries = [call for call in store.fetch_all_calls if "user_job_daily_metrics" in call[0]]
    assert "new_global_jobs_count" in global_query
    assert all("new_user_jobs_count" in statement for statement, _ in user_queries)
    assert all("new_applied_jobs_count" in statement for statement, _ in user_queries)
    assert user_queries[0][1][0] == USER_A
    assert user_queries[0][1][3] == USER_A
    assert user_queries[1][1][0] == USER_B
    assert user_queries[1][1][3] == USER_B


def test_current_funnel_reads_latest_maintained_tenant_snapshot() -> None:
    store = _Store()
    store.funnels[USER_A] = {
        "global_jobs_count": 5,
        "user_jobs_count": 4,
        "applied_jobs_count": 3,
        "interview_jobs_count": 2,
    }
    repository = DashboardAnalyticsRepository(store)  # type: ignore[arg-type]

    repository.get_current_funnel(user_uuid=USER_A)

    statement, params = store.fetch_one_calls[0]
    assert "from public.user_job_daily_metrics" in statement
    assert "from public.global_job_daily_metrics" in statement
    assert "user_job_status_events" not in statement
    assert params == [USER_A, False]


@pytest.mark.parametrize("days", [0, 6, 366])
def test_repository_rejects_out_of_range_windows(days: int) -> None:
    repository = DashboardAnalyticsRepository(_Store())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="between 7 and 365"):
        repository.get_analytics(user_uuid=USER_A, days=days)
