from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from apps.api.routers.data_freshness import data_freshness
from apps.scheduler import main as scheduler_main
from packages.careersignal_core.scheduling import (
    ScheduleConfigurationError,
    get_connector_refresh_schedule,
    get_current_and_next_fire_times,
    get_next_connector_refresh_at,
)
from packages.careersignal_core.tasks.connector_refresh_task import (
    enqueue_scheduled_connector_refresh,
)
from packages.careersignal_core.repositories.errors import ConflictError


def _settings(**overrides):
    values = {
        "connector_refresh_trigger_mode": "scheduled",
        "connector_refresh_cron": "0 7,16,21 * * *",
        "connector_refresh_timezone": "America/New_York",
        "connector_stale_after_hours": 8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_multiple_daily_occurrences_are_calculated_in_scheduler_timezone() -> None:
    schedule = get_connector_refresh_schedule(_settings())
    assert schedule is not None

    next_fire = schedule.next_fire_time(
        after=datetime(2026, 7, 11, 10, 30, tzinfo=timezone.utc)
    )
    current, following = get_current_and_next_fire_times(
        schedule,
        scheduled_for=next_fire,
    )

    assert current == datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc)
    assert following == datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc)
    assert current.utcoffset() is not None
    assert following.utcoffset() is not None


def test_dst_fall_back_preserves_both_apscheduler_occurrences() -> None:
    schedule = get_connector_refresh_schedule(_settings(connector_refresh_cron="0 1 * * *"))
    assert schedule is not None
    first = schedule.next_fire_time(
        after=datetime(2026, 11, 1, 4, 30, tzinfo=timezone.utc)
    )
    _, second = get_current_and_next_fire_times(schedule, scheduled_for=first)

    assert first == datetime(2026, 11, 1, 5, 0, tzinfo=timezone.utc)
    assert second == datetime(2026, 11, 1, 6, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("overrides", "setting_name"),
    [
        ({"connector_refresh_cron": "not a cron"}, "CONNECTOR_REFRESH_CRON"),
        ({"connector_refresh_timezone": "Mars/Olympus_Mons"}, "CONNECTOR_REFRESH_TIMEZONE"),
    ],
)
def test_scheduler_startup_rejects_invalid_schedule(monkeypatch, overrides, setting_name) -> None:
    monkeypatch.setattr(scheduler_main, "get_settings", lambda: _settings(**overrides))

    with pytest.raises(ScheduleConfigurationError, match=setting_name):
        scheduler_main.build_scheduler()


def test_scheduler_startup_validates_configuration_even_when_schedule_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        scheduler_main,
        "get_settings",
        lambda: _settings(
            connector_refresh_trigger_mode="first_user_bootstrap",
            connector_refresh_timezone="not/a-zone",
        ),
    )

    with pytest.raises(ScheduleConfigurationError, match="CONNECTOR_REFRESH_TIMEZONE"):
        scheduler_main.build_scheduler()


class CapturingRepository:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.calls = []

    def create_if_no_active(self, **kwargs):
        self.calls.append(kwargs)
        if self.conflict:
            raise ConflictError("active")
        return {
            "connector_run_uuid": "11111111-1111-4111-8111-111111111111",
            "status": "queued",
            "trigger_type": kwargs["trigger_type"],
        }


def test_scheduler_event_persists_exact_current_and_next_occurrences() -> None:
    repository = CapturingRepository()
    schedule = get_connector_refresh_schedule(_settings())
    assert schedule is not None
    event = SimpleNamespace(
        job_id="global-connector-refresh",
        scheduled_run_time=datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),
    )

    scheduler_main._enqueue_scheduled_event(event, schedule=schedule, repository=repository)

    assert repository.calls == [
        {
            "trigger_type": "scheduled",
            "scheduled_for": datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),
            "next_scheduled_at": datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc),
        }
    ]


def test_active_run_skips_scheduled_occurrence_without_second_create() -> None:
    repository = CapturingRepository(conflict=True)
    result = enqueue_scheduled_connector_refresh(
        repository=repository,
        scheduled_for=datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),
        next_scheduled_at=datetime(2026, 7, 11, 20, 0, tzinfo=timezone.utc),
    )

    assert result["status"] == "skipped"
    assert len(repository.calls) == 1


class FreshnessRepository:
    def freshness(self, *, stale_after_hours: int):
        return {"overall": {"next_scheduled_refresh_at": None}, "sources": []}


def test_data_freshness_exposes_computed_next_schedule(monkeypatch) -> None:
    expected = datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "apps.api.routers.data_freshness.get_next_connector_refresh_at",
        lambda settings: expected,
    )

    result = data_freshness(None, FreshnessRepository(), _settings())

    assert result["overall"]["next_scheduled_refresh_at"] == expected


def test_scheduling_disabled_has_no_next_refresh() -> None:
    settings = _settings(connector_refresh_trigger_mode="first_user_bootstrap")

    assert get_next_connector_refresh_at(settings) is None
