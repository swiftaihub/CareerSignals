"""Canonical APScheduler-compatible connector refresh schedule calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.triggers.cron import CronTrigger

from packages.careersignal_core.settings import AppSettings


class ScheduleConfigurationError(ValueError):
    """Raised when connector scheduling configuration cannot be used safely."""


@dataclass(frozen=True)
class ConnectorRefreshSchedule:
    cron: str
    timezone: ZoneInfo
    trigger: CronTrigger

    def next_fire_time(self, *, after: datetime | None = None) -> datetime:
        reference = after or datetime.now(timezone.utc)
        _require_aware(reference, name="after")
        fire_time = self.trigger.get_next_fire_time(None, reference.astimezone(self.timezone))
        if fire_time is None:  # pragma: no cover - a five-field cron is recurring
            raise ScheduleConfigurationError(
                f"CONNECTOR_REFRESH_CRON={self.cron!r} does not produce a future occurrence"
            )
        return fire_time.astimezone(timezone.utc)


def _require_aware(value: datetime, *, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def get_connector_refresh_schedule(
    settings: AppSettings,
    *,
    validate_when_disabled: bool = False,
) -> ConnectorRefreshSchedule | None:
    """Build the one canonical trigger used by the scheduler and status API."""

    enabled = settings.connector_refresh_trigger_mode in {"scheduled", "both"}
    if not enabled and not validate_when_disabled:
        return None
    try:
        schedule_timezone = ZoneInfo(settings.connector_refresh_timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ScheduleConfigurationError(
            "Invalid CONNECTOR_REFRESH_TIMEZONE "
            f"{settings.connector_refresh_timezone!r}; use an IANA name such as America/New_York"
        ) from exc
    try:
        trigger = CronTrigger.from_crontab(
            settings.connector_refresh_cron,
            timezone=schedule_timezone,
        )
    except (TypeError, ValueError) as exc:
        raise ScheduleConfigurationError(
            "Invalid CONNECTOR_REFRESH_CRON "
            f"{settings.connector_refresh_cron!r}; expected a five-field cron expression"
        ) from exc
    schedule = ConnectorRefreshSchedule(
        cron=settings.connector_refresh_cron,
        timezone=schedule_timezone,
        trigger=trigger,
    )
    return schedule if enabled else None


def get_current_and_next_fire_times(
    schedule: ConnectorRefreshSchedule,
    *,
    scheduled_for: datetime,
) -> tuple[datetime, datetime]:
    """Normalize an APScheduler occurrence and its successor to UTC."""

    _require_aware(scheduled_for, name="scheduled_for")
    local_occurrence = scheduled_for.astimezone(schedule.timezone)
    next_fire_time = schedule.trigger.get_next_fire_time(local_occurrence, local_occurrence)
    if next_fire_time is None:  # pragma: no cover - a five-field cron is recurring
        raise ScheduleConfigurationError(
            f"CONNECTOR_REFRESH_CRON={schedule.cron!r} has no occurrence after {scheduled_for.isoformat()}"
        )
    return (
        local_occurrence.astimezone(timezone.utc),
        next_fire_time.astimezone(timezone.utc),
    )


def get_next_connector_refresh_at(
    settings: AppSettings,
    *,
    now: datetime | None = None,
) -> datetime | None:
    schedule = get_connector_refresh_schedule(settings)
    return None if schedule is None else schedule.next_fire_time(after=now)
