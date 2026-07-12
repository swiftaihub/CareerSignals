"""Deprecated compatibility wrapper for the trusted shared Connector refresh."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _preferred_workspace_python() -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable_name = "python.exe" if os.name == "nt" else "python"
    return PROJECT_ROOT / ".venv311" / scripts_dir / executable_name


def _running_preferred_python(preferred_python: Path) -> bool:
    try:
        return Path(sys.executable).resolve() == preferred_python.resolve()
    except OSError:
        return False


def _reexec_with_workspace_python() -> None:
    preferred_python = _preferred_workspace_python()
    if (
        os.getenv("CAREERSIGNAL_SKIP_PYTHON_REEXEC")
        or not preferred_python.exists()
        or _running_preferred_python(preferred_python)
    ):
        return

    os.execv(str(preferred_python), [str(preferred_python), *sys.argv])


if __name__ == "__main__":
    _reexec_with_workspace_python()

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from src.pipelines.shared_connector_refresh import run_shared_connector_refresh
from src.utils.logging import configure_logging


def _print_summary(summary: dict[str, Any]) -> None:
    print("CareerSignal shared Connector refresh completed.")
    print(f"Connector run UUID: {summary['connector_run_uuid']}")
    print(f"Fetched jobs: {summary['fetched_raw_jobs']}")
    print(f"Freshness filtered out: {summary['freshness_filtered_out']}")
    print(f"Raw jobs written: {summary['raw_jobs']}")
    print(f"Shared jobs: {summary['shared_jobs']}")
    print(f"dbt completed: {summary['dbt_completed']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Deprecated name: run the trusted shared Connector refresh. "
            "This command never runs user models."
        )
    )
    parser.add_argument("--connector-run-uuid")
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")

    configure_logging()
    summary = run_shared_connector_refresh(
        args.connector_run_uuid,
        project_root=PROJECT_ROOT,
    )
    _print_summary(summary)


if __name__ == "__main__":
    main()
