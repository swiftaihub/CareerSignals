"""Run the global connector scheduler in a dedicated process."""

from __future__ import annotations

import logging

from apscheduler.events import EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.blocking import BlockingScheduler

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.scheduling import (
    ConnectorRefreshSchedule,
    get_connector_refresh_schedule,
    get_current_and_next_fire_times,
)
from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.tasks.connector_refresh_task import enqueue_scheduled_connector_refresh

LOGGER = logging.getLogger(__name__)


def _scheduler_tick() -> None:
    """APScheduler target; the execution event carries the exact fire time."""


def _enqueue_scheduled_event(
    event: JobExecutionEvent,
    *,
    schedule: ConnectorRefreshSchedule,
    repository: ConnectorRunRepository | None = None,
) -> None:
    if event.job_id != "global-connector-refresh":
        return
    scheduled_for, next_scheduled_at = get_current_and_next_fire_times(
        schedule,
        scheduled_for=event.scheduled_run_time,
    )
    result = enqueue_scheduled_connector_refresh(
        repository=repository,
        scheduled_for=scheduled_for,
        next_scheduled_at=next_scheduled_at,
    )
    LOGGER.info(
        "Processed scheduled global connector refresh occurrence",
        extra={
            "connector_run_uuid": str(result.get("connector_run_uuid") or ""),
            "trigger_type": "scheduled",
            "scheduled_for": scheduled_for.isoformat(),
            "next_scheduled_at": next_scheduled_at.isoformat(),
            "execution_status": result.get("status"),
        },
    )


def build_scheduler(
    *, repository: ConnectorRunRepository | None = None
) -> BlockingScheduler:
    settings = get_settings()
    schedule = get_connector_refresh_schedule(settings, validate_when_disabled=True)
    scheduler = BlockingScheduler(timezone=schedule.timezone if schedule else "UTC")
    if schedule is not None:
        scheduler.add_job(
            _scheduler_tick,
            schedule.trigger,
            id="global-connector-refresh",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=900,
            replace_existing=True,
        )
        scheduler.add_listener(
            lambda event: _enqueue_scheduled_event(
                event,
                schedule=schedule,
                repository=repository,
            ),
            EVENT_JOB_EXECUTED,
        )
    return scheduler


def main() -> None:
    settings = get_settings()
    settings.require_api_configuration()
    logging.basicConfig(level=settings.log_level)
    build_scheduler().start()


if __name__ == "__main__":
    main()
