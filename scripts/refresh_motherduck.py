"""Run API ingestion, MotherDuck bridge writes, and dbt refresh."""

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

from src.main import run_pipeline
from src.utils.logging import configure_logging


def _print_summary(summary: dict[str, Any]) -> None:
    print("CareerSignal MotherDuck refresh completed.")
    print(f"Run ID: {summary['run_id']}")
    print(f"Fetched jobs: {summary['fetched_raw_jobs']}")
    print(f"Freshness filtered out: {summary['freshness_filtered_out']}")
    print(f"Raw jobs written: {summary['raw_jobs']}")
    print(f"Processed jobs: {summary['total_jobs_processed']}")
    print(f"Deduplicated jobs: {summary['deduplicated_jobs']}")
    print(f"Top matches: {summary['top_matches']}")
    if summary.get("output_path"):
        print(f"Excel exported to: {Path(summary['output_path']).resolve()}")
    else:
        print("Excel export skipped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full CareerSignal MotherDuck refresh path."
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run dbt incrementally instead of using --full-refresh.",
    )
    parser.add_argument(
        "--skip-dbt-tests",
        action="store_true",
        help="Skip dbt tests after dbt run.",
    )
    parser.add_argument(
        "--sources",
        help="Override JOB_SOURCES for this run, for example greenhouse,adzuna.",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Also write a timestamped Excel workbook to the local outputs directory.",
    )
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")

    os.environ["CAREERSIGNAL_DATA_MODE"] = "motherduck"
    os.environ["DBT_TARGET"] = "dev"
    os.environ["CAREERSIGNAL_RUN_DBT"] = "true"
    os.environ["CAREERSIGNAL_DBT_FULL_REFRESH"] = "false" if args.incremental else "true"
    os.environ["CAREERSIGNAL_EXPORT_EXCEL"] = "true" if args.export_excel else "false"
    if args.skip_dbt_tests:
        os.environ["CAREERSIGNAL_RUN_DBT_TESTS"] = "false"
    if args.sources:
        os.environ["JOB_SOURCES"] = args.sources

    configure_logging()
    summary = run_pipeline(PROJECT_ROOT)
    _print_summary(summary)


if __name__ == "__main__":
    main()
