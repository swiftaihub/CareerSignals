"""Run the global connector scheduler in a dedicated process."""

from __future__ import annotations

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.tasks.connector_refresh_task import run_scheduled_connector_refresh


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=settings.connector_refresh_timezone)
    scheduler.add_job(
        run_scheduled_connector_refresh,
        CronTrigger.from_crontab(
            settings.connector_refresh_cron, timezone=settings.connector_refresh_timezone
        ),
        id="global-connector-refresh",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=900,
        replace_existing=True,
    )
    return scheduler


def main() -> None:
    settings = get_settings()
    settings.require_api_configuration()
    logging.basicConfig(level=settings.log_level)
    build_scheduler().start()


if __name__ == "__main__":
    main()
