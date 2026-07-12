"""Enqueue a production-equivalent global connector refresh for the worker."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.errors import ConflictError
from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.tasks.connector_refresh_task import enqueue_connector_refresh
from src.utils.logging import configure_logging


def main(
    argv: Sequence[str] | None = None,
    *,
    repository: ConnectorRunRepository | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enqueue the complete shared connector, MotherDuck, dbt, and PostgreSQL "
            "publication pipeline. The apps.worker process performs the refresh."
        )
    )
    parser.add_argument(
        "--enqueue",
        action="store_true",
        help="Enqueue the refresh (the default; retained for an explicit operator workflow).",
    )
    parser.parse_args(argv)
    configure_logging()
    settings = get_settings()
    settings.require_api_configuration()
    repo = repository or ConnectorRunRepository()
    try:
        run = enqueue_connector_refresh(repository=repo, trigger_type="manual_cli")
    except ConflictError:
        print(
            "Cannot enqueue: a global connector refresh is already queued or running.",
            file=sys.stderr,
        )
        return 2

    print("CareerSignals global refresh queued.")
    print(f"Connector run UUID: {run['connector_run_uuid']}")
    print("Ensure apps.worker is running: python -m apps.worker.main")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
