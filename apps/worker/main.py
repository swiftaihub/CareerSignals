"""Run with ``python -m apps.worker.main``."""

from __future__ import annotations

import logging
import threading

from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.tasks.connector_refresh_worker import ConnectorRefreshWorker
from packages.careersignal_core.tasks.user_pipeline_worker import UserPipelineWorker


def main() -> None:
    settings = get_settings()
    settings.require_api_configuration()
    logging.basicConfig(level=settings.log_level)
    stop_event = threading.Event()
    connector_worker = ConnectorRefreshWorker(settings=settings)
    user_worker = UserPipelineWorker(settings=settings)
    logging.getLogger(__name__).info("CareerSignals worker started")
    while not stop_event.is_set():
        processed_global = connector_worker.process_one()
        processed_user = False if processed_global else user_worker.process_one()
        if not processed_global and not processed_user:
            stop_event.wait(settings.user_pipeline_poll_seconds)


if __name__ == "__main__":
    main()
