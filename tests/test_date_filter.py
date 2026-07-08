from __future__ import annotations

from datetime import datetime, timezone

from src.config.schemas import FreshnessFilter
from src.processing.date_filter import (
    filter_jobs_by_posted_date,
    freshness_decision,
    parse_posted_date,
)


def test_parse_relative_posted_date() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)

    parsed = parse_posted_date("2 hours ago", now)

    assert parsed is not None
    assert parsed.posted_at == datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc)


def test_freshness_decision_keeps_iso_timestamp_within_24_hours() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    config = FreshnessFilter(enabled=True, max_post_age_hours=24)
    job = {"date_posted": "2026-07-07T13:00:00Z"}

    decision = freshness_decision(job, config, now)

    assert decision.keep is True
    assert decision.reason == "fresh"


def test_freshness_decision_drops_relative_date_older_than_24_hours() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    config = FreshnessFilter(enabled=True, max_post_age_hours=24)
    job = {"date_posted": "2 days ago"}

    decision = freshness_decision(job, config, now)

    assert decision.keep is False
    assert decision.reason == "older_than_max_age"


def test_freshness_decision_keeps_date_only_values_on_cutoff_date() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    config = FreshnessFilter(enabled=True, max_post_age_hours=24)
    job = {"date_posted": "2026-07-07"}

    decision = freshness_decision(job, config, now)

    assert decision.keep is True
    assert decision.reason == "fresh_date_only"


def test_freshness_decision_excludes_unknown_dates_by_default() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    config = FreshnessFilter(enabled=True, max_post_age_hours=24)
    job = {"date_posted": None}

    decision = freshness_decision(job, config, now)

    assert decision.keep is False
    assert decision.reason == "unknown_date_excluded"


def test_filter_jobs_by_posted_date_reports_stats() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    config = FreshnessFilter(enabled=True, max_post_age_hours=24)
    jobs = [
        {"date_posted": "2026-07-08T10:00:00Z"},
        {"date_posted": "3 days ago"},
        {"date_posted": None},
    ]

    filtered, stats = filter_jobs_by_posted_date(jobs, config, now)

    assert len(filtered) == 1
    assert stats["input_jobs"] == 3
    assert stats["kept_jobs"] == 1
    assert stats["older_than_max_age"] == 1
    assert stats["unknown_date_excluded"] == 1
