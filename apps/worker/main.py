"""Run with ``python -m apps.worker.main``."""

from __future__ import annotations

import logging

from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.tasks.user_pipeline_worker import UserPipelineWorker


def main() -> None:
    settings = get_settings()
    settings.require_api_configuration()
    logging.basicConfig(level=settings.log_level)
    UserPipelineWorker(settings=settings).run_forever()


if __name__ == "__main__":
    main()
