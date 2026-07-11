"""Run the trusted platform Connector refresh process."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.shared_connector_refresh import run_shared_connector_refresh
from src.utils.logging import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh the shared job universe from system-owned Connector configuration."
    )
    parser.add_argument(
        "--connector-run-uuid",
        help="Optional scheduler-created Connector run UUID.",
    )
    args = parser.parse_args()
    configure_logging()
    summary = run_shared_connector_refresh(
        args.connector_run_uuid,
        project_root=PROJECT_ROOT,
    )
    print("CareerSignal shared Connector refresh completed.")
    print(f"Connector run UUID: {summary['connector_run_uuid']}")
    print(f"Fetched jobs: {summary['fetched_raw_jobs']}")
    print(f"Shared jobs: {summary['shared_jobs']}")
    print(f"dbt completed: {summary['dbt_completed']}")


if __name__ == "__main__":
    main()
