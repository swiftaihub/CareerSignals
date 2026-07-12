"""Backward-compatible entry point for the system shared refresh.

The legacy monolithic pipeline has been split.  This module is deliberately a
thin wrapper and is not a user dbt refresh entry point.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.schemas import ConfigBundle
from src.pipelines import shared_connector_refresh as _shared
from src.pipelines.shared_processing import (
    apply_shared_freshness_filter,
    enrich_shared_jobs,
    normalize_shared_jobs,
)


def source_names_from_env() -> list[str]:
    raw = os.getenv("JOB_SOURCES") or os.getenv("JOB_SOURCE") or "mock"
    values = [item.strip().casefold() for item in raw.split(",") if item.strip()]
    if "all" in values:
        return ["adzuna", "serpapi", "greenhouse", "lever", "usajobs"]
    return values or ["mock"]


build_connector = _shared.build_connector
build_connectors = _shared.build_connectors
_collect_jobs = _shared.collect_connector_jobs
_normalize_jobs = normalize_shared_jobs
_enrich_and_score_jobs = enrich_shared_jobs


def _apply_freshness_filter(
    raw_records: list[dict[str, Any]],
    normalized_jobs: list[dict[str, Any]],
    configs: ConfigBundle,
    progress: Any | None = None,
):
    return apply_shared_freshness_filter(
        raw_records,
        normalized_jobs,
        configs.platform_connector.freshness_filter,
        progress,
    )


def run_pipeline(project_root: str | Path = ".") -> dict[str, Any]:
    """Deprecated alias for the trusted global Connector refresh."""

    # Preserve monkeypatch-based regression tests without putting pipeline logic
    # back into this compatibility module.
    _shared.MotherDuckService = MotherDuckService
    _shared.MotherDuckIngestionWriter = MotherDuckIngestionWriter
    _shared.init_motherduck_schema = init_motherduck_schema
    return _shared.run_shared_connector_refresh(project_root=project_root)


def export_excel_from_current_data(project_root: str | Path = ".") -> Path:
    """Fail closed until an authenticated user-scoped export service is used."""

    raise RuntimeError(
        "Global Excel export is disabled in SaaS mode; use the authenticated "
        "user partition export service"
    )


def main() -> None:
    summary = run_pipeline(Path(__file__).resolve().parents[1])
    print("CareerSignal shared Connector refresh completed.")
    print(f"Connector run UUID: {summary['connector_run_uuid']}")
    print(f"Fetched jobs: {summary['fetched_raw_jobs']}")
    print(f"Shared jobs: {summary['shared_jobs']}")


if __name__ == "__main__":
    main()
