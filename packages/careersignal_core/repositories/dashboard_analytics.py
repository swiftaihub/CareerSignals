"""Indexed PostgreSQL reads and atomic snapshot writes for Dashboard analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping
from zoneinfo import ZoneInfo

from packages.careersignal_core.storage.postgres import PostgresStore


DASHBOARD_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class DashboardFunnelMetrics:
    total_global_jobs: int
    total_user_jobs: int
    total_applied_jobs: int
    total_interviews: int

    def as_dict(self) -> dict[str, int]:
        return {
            "total_global_jobs": self.total_global_jobs,
            "total_user_jobs": self.total_user_jobs,
            "total_applied_jobs": self.total_applied_jobs,
            "total_interviews": self.total_interviews,
        }


@dataclass(frozen=True)
class JobCountTimeseriesPoint:
    date: date
    global_jobs: int | None
    user_jobs: int | None
    applied_jobs: int | None

    def as_dict(self) -> dict[str, date | int | None]:
        return {
            "date": self.date,
            "global_jobs": self.global_jobs,
            "user_jobs": self.user_jobs,
            "applied_jobs": self.applied_jobs,
        }


@dataclass(frozen=True)
class DashboardAnalyticsResult:
    funnel: DashboardFunnelMetrics
    job_count_timeseries: list[JobCountTimeseriesPoint]
    start_date: date
    end_date: date
    days: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "funnel": self.funnel.as_dict(),
            "job_count_timeseries": [point.as_dict() for point in self.job_count_timeseries],
            "analytics_window": {
                "start_date": self.start_date,
                "end_date": self.end_date,
                "days": self.days,
            },
        }


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def build_daily_timeseries(
    *,
    global_rows: Iterable[Mapping[str, Any]],
    user_rows: Iterable[Mapping[str, Any]],
    start_date: date,
    end_date: date,
    is_demo: bool = False,
) -> list[JobCountTimeseriesPoint]:
    """Carry known end-of-day values forward, preserving unknown leading dates."""

    global_by_date = {_as_date(row["metric_date"]): row for row in global_rows}
    user_by_date = {_as_date(row["metric_date"]): row for row in user_rows}
    prior_global_dates = [metric_date for metric_date in global_by_date if metric_date < start_date]
    prior_user_dates = [metric_date for metric_date in user_by_date if metric_date < start_date]
    prior_global = global_by_date[max(prior_global_dates)] if prior_global_dates else None
    prior_user = user_by_date[max(prior_user_dates)] if prior_user_dates else None
    global_jobs = (
        int(prior_global["global_jobs_count"]) if prior_global is not None else None
    )
    user_jobs = int(prior_user["user_jobs_count"]) if prior_user is not None else None
    applied_jobs = int(prior_user["applied_jobs_count"]) if prior_user is not None else None
    points: list[JobCountTimeseriesPoint] = []
    cursor = start_date
    while cursor <= end_date:
        global_row = global_by_date.get(cursor)
        if global_row is not None:
            global_jobs = int(global_row["global_jobs_count"])
        user_row = user_by_date.get(cursor)
        if user_row is not None:
            user_jobs = int(user_row["user_jobs_count"])
            applied_jobs = int(user_row["applied_jobs_count"])
        point = JobCountTimeseriesPoint(
            date=cursor,
            global_jobs=user_jobs if is_demo else global_jobs,
            user_jobs=user_jobs,
            applied_jobs=applied_jobs,
        )
        if any(
            value is not None
            for value in (point.global_jobs, point.user_jobs, point.applied_jobs)
        ):
            points.append(point)
        cursor += timedelta(days=1)
    return points


class DashboardAnalyticsRepository:
    """All analytics SQL is centralized here for publication and request paths."""

    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def record_global_snapshot(
        self,
        *,
        connector_run_uuid: str | None = None,
        metric_date: date | None = None,
        connection: Any | None = None,
    ) -> None:
        snapshot_date = metric_date or datetime.now(DASHBOARD_TIMEZONE).date()
        statement = "select public.upsert_global_job_daily_metric(%s::uuid, %s)"
        params = [connector_run_uuid, snapshot_date]
        if connection is not None:
            connection.execute(statement, params)
            return
        with self.store.transaction() as transaction:
            transaction.execute(statement, params)

    def record_user_snapshot(
        self,
        *,
        user_uuid: str,
        personal_run_uuid: str | None = None,
        metric_date: date | None = None,
        connection: Any | None = None,
    ) -> None:
        if not user_uuid:
            raise ValueError("A verified user UUID is required")
        snapshot_date = metric_date or datetime.now(DASHBOARD_TIMEZONE).date()
        statement = "select public.upsert_user_job_daily_metric(%s::uuid, %s::uuid, %s)"
        params = [user_uuid, personal_run_uuid, snapshot_date]
        if connection is not None:
            connection.execute(statement, params)
            return
        with self.store.transaction() as transaction:
            transaction.execute(statement, params)

    def get_current_funnel(
        self, *, user_uuid: str, is_demo: bool = False
    ) -> DashboardFunnelMetrics:
        if not user_uuid:
            raise ValueError("A verified user UUID is required")
        row = self.store.fetch_one(
            """
            with latest_global as (
                select global_jobs_count
                from public.global_job_daily_metrics
                order by metric_date desc
                limit 1
            ),
            latest_user as (
                select user_jobs_count, applied_jobs_count, interview_jobs_count
                from public.user_job_daily_metrics
                where user_uuid = %s::uuid
                order by metric_date desc
                limit 1
            )
            select
                case
                    when %s then coalesce((select user_jobs_count from latest_user), 0)
                    else coalesce((select global_jobs_count from latest_global), 0)
                end as global_jobs_count,
                coalesce((select user_jobs_count from latest_user), 0) as user_jobs_count,
                coalesce((select applied_jobs_count from latest_user), 0) as applied_jobs_count,
                coalesce((select interview_jobs_count from latest_user), 0) as interview_jobs_count
            """,
            [user_uuid, is_demo],
        ) or {}
        return DashboardFunnelMetrics(
            total_global_jobs=int(row.get("global_jobs_count") or 0),
            total_user_jobs=int(row.get("user_jobs_count") or 0),
            total_applied_jobs=int(row.get("applied_jobs_count") or 0),
            total_interviews=int(row.get("interview_jobs_count") or 0),
        )

    def get_analytics(
        self,
        *,
        user_uuid: str,
        days: int = 30,
        is_demo: bool = False,
        end_date: date | None = None,
    ) -> DashboardAnalyticsResult:
        if not 7 <= days <= 365:
            raise ValueError("days must be between 7 and 365")
        if not user_uuid:
            raise ValueError("A verified user UUID is required")
        window_end = end_date or datetime.now(DASHBOARD_TIMEZONE).date()
        window_start = window_end - timedelta(days=days - 1)

        global_rows = (
            []
            if is_demo
            else self.store.fetch_all(
                """
                select metric_date, global_jobs_count
                from public.global_job_daily_metrics
                where metric_date between %s and %s
                   or metric_date = (
                        select max(previous.metric_date)
                        from public.global_job_daily_metrics as previous
                        where previous.metric_date < %s
                   )
                order by metric_date
                """,
                [window_start, window_end, window_start],
            )
        )
        user_rows = self.store.fetch_all(
            """
            select metric_date, user_jobs_count, applied_jobs_count
            from public.user_job_daily_metrics
            where user_uuid = %s::uuid
              and (
                    metric_date between %s and %s
                    or metric_date = (
                        select max(previous.metric_date)
                        from public.user_job_daily_metrics as previous
                        where previous.user_uuid = %s::uuid
                          and previous.metric_date < %s
                    )
              )
            order by metric_date
            """,
            [user_uuid, window_start, window_end, user_uuid, window_start],
        )
        return DashboardAnalyticsResult(
            funnel=self.get_current_funnel(user_uuid=user_uuid, is_demo=is_demo),
            job_count_timeseries=build_daily_timeseries(
                global_rows=global_rows,
                user_rows=user_rows,
                start_date=window_start,
                end_date=window_end,
                is_demo=is_demo,
            ),
            start_date=window_start,
            end_date=window_end,
            days=days,
        )
