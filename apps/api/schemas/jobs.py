from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import Field

from apps.api.schemas.common import APIModel


class JobStatusUpdate(APIModel):
    application_status: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=4000)


class DashboardMetrics(APIModel):
    total_jobs: int
    top_matches: int
    average_match_score: float | None = None
    average_salary_midpoint: float | None = None
    remote_or_hybrid_roles: int
    positive_or_unknown_visa_roles: int


class DashboardDistributionRow(APIModel):
    label: str
    count: int


class DashboardFunnel(APIModel):
    total_global_jobs: int
    total_user_jobs: int
    total_applied_jobs: int
    total_interviews: int


class JobCountTimeseriesPoint(APIModel):
    date: date
    global_jobs: int | None
    user_jobs: int | None
    applied_jobs: int | None


class DashboardAnalyticsWindow(APIModel):
    start_date: date
    end_date: date
    days: int = Field(ge=7, le=365)


class DashboardSummary(APIModel):
    # These legacy sections deliberately retain their flexible row contracts.
    # The new analytics fields below are fully typed without breaking existing
    # Dashboard consumers that depend on dimension-specific attributes.
    data_status: dict[str, Any]
    metrics: DashboardMetrics
    category_summary: list[dict[str, Any]]
    top_matches_preview: list[dict[str, Any]]
    visa_signal_distribution: list[DashboardDistributionRow]
    work_arrangement_distribution: list[DashboardDistributionRow]
    match_tier_distribution: list[DashboardDistributionRow]
    funnel: DashboardFunnel
    job_count_timeseries: list[JobCountTimeseriesPoint]
    analytics_window: DashboardAnalyticsWindow
