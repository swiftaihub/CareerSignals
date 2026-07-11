"""Trusted system-only Connector refresh for the shared job universe."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any, Iterable
from uuid import UUID, uuid4

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from packages.careersignal_core.dbt.runner import run_shared_dbt_build
from packages.careersignal_core.settings import bool_env, data_mode, dbt_profiles_dir, dbt_project_dir
from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.loader import load_configs
from src.config.schemas import ConfigBundle, ConnectorRetryConfig, JobCategoryConfig
from src.connectors.adzuna_connector import AdzunaConnector
from src.connectors.base import BaseJobConnector
from src.connectors.greenhouse_connector import GreenhouseConnector
from src.connectors.lever_connector import LeverConnector
from src.connectors.mock_connector import MockJobConnector
from src.connectors.serpapi_connector import SerpApiConnector
from src.connectors.usajobs_connector import USAJobsConnector
from src.ingestion.persistence import write_json_snapshot
from src.pipelines.shared_processing import (
    apply_shared_freshness_filter,
    enrich_shared_jobs,
    normalize_shared_jobs,
)
from src.processing.deduplicate import deduplicate_jobs
from src.utils.progress import ProgressReporter

LOGGER = logging.getLogger(__name__)


def _uses_motherduck_analytics(mode: str) -> bool:
    """Return whether the shared bridge must feed the MotherDuck dbt target.

    In SaaS, ``CAREERSIGNAL_DATA_MODE=postgres`` describes the serving layer,
    while dbt still runs against MotherDuck. Treating it as a mutually
    exclusive storage choice silently discarded every shared refresh.
    """

    if mode == "motherduck":
        return True
    return (
        os.getenv("DBT_TARGET", "").strip().casefold() == "dev"
        and bool(os.getenv("MOTHERDUCK_TOKEN", "").strip())
    )


def source_names_from_config(configs: ConfigBundle) -> list[str]:
    """Use an operator override or the repository-owned platform source list."""

    raw_sources = os.getenv("JOB_SOURCES") or os.getenv("JOB_SOURCE")
    if raw_sources:
        sources = [item.strip().casefold() for item in raw_sources.split(",") if item.strip()]
    else:
        sources = list(configs.platform_connector.enabled_sources)
    if "all" in sources:
        return ["adzuna", "serpapi", "greenhouse", "lever", "usajobs"]
    return sources or ["mock"]


def build_connector(
    source_name: str,
    project_root: Path,
    configs: ConfigBundle,
) -> BaseJobConnector:
    normalized = source_name.casefold().strip()
    filters = configs.platform_connector.global_filters
    if normalized == "adzuna":
        connector: BaseJobConnector = AdzunaConnector(global_filters=filters)
    elif normalized in {"serpapi", "serpapi_google_jobs", "google_jobs"}:
        connector = SerpApiConnector(global_filters=filters)
    elif normalized == "greenhouse":
        connector = GreenhouseConnector(global_filters=filters)
    elif normalized == "lever":
        connector = LeverConnector(global_filters=filters)
    elif normalized in {"usajobs", "usa_jobs"}:
        connector = USAJobsConnector(global_filters=filters)
    else:
        connector = MockJobConnector(project_root / "data" / "sample" / "sample_jobs.json")

    budget = configs.platform_connector.source_budgets.get(normalized)
    if budget is not None:
        if hasattr(connector, "max_pages"):
            setattr(connector, "max_pages", budget.page_limit)
        if hasattr(connector, "max_queries_per_category"):
            setattr(connector, "max_queries_per_category", budget.query_limit_per_category)
    if hasattr(connector, "timeout"):
        setattr(connector, "timeout", configs.platform_connector.retry.timeout_seconds)
    return connector


def build_connectors(
    source_names: list[str], project_root: Path, configs: ConfigBundle
) -> list[BaseJobConnector]:
    return [build_connector(name, project_root, configs) for name in source_names]


def collect_connector_jobs(
    connectors: list[BaseJobConnector],
    categories: list[JobCategoryConfig],
    progress: ProgressReporter | None = None,
    retry: ConnectorRetryConfig | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    work = [(connector, category) for connector in connectors for category in categories]
    iterable: Iterable[tuple[BaseJobConnector, JobCategoryConfig]] = (
        progress.iter(work, "Fetching shared Connector jobs", total=len(work))
        if progress
        else work
    )
    for connector, category in iterable:
        policy = retry or ConnectorRetryConfig(max_attempts=1, backoff_seconds=0)
        fetched: list[dict[str, Any]] | None = None
        for attempt in range(1, policy.max_attempts + 1):
            try:
                fetched = connector.fetch_jobs(category)
                break
            except Exception as exc:  # one source must not prevent other sources
                if attempt < policy.max_attempts:
                    LOGGER.warning(
                        "Connector %s failed for category %s (attempt %s/%s)",
                        connector.source_name,
                        category.category_name,
                        attempt,
                        policy.max_attempts,
                    )
                    if policy.backoff_seconds:
                        time.sleep(policy.backoff_seconds * attempt)
                    continue
                LOGGER.exception(
                    "Connector %s failed for category %s",
                    connector.source_name,
                    category.category_name,
                )
                errors.append(
                    {
                        "source": connector.source_name,
                        "category_name": category.category_name,
                        "query_title": ", ".join(category.search_titles),
                        "error_message": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )
        if fetched is None:
            continue
        raw_records.extend(
            {
                **record,
                "_careersignal_category": category,
                "_careersignal_source": connector.source_name,
            }
            for record in fetched
        )
    return raw_records, errors


def _source_results(
    connectors: list[BaseJobConnector],
    raw_records: list[dict[str, Any]],
    shared_jobs: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for connector in connectors:
        source = connector.source_name
        if source in seen:
            continue
        seen.add(source)
        fetched = sum(1 for row in raw_records if row.get("_careersignal_source") == source)
        retained = sum(1 for row in shared_jobs if row.get("source") == source)
        source_errors = [row for row in errors if row.get("source") == source]
        if source_errors:
            status = "partial" if fetched else "failed"
            message = "Some source queries failed." if fetched else "The source refresh failed."
        else:
            status = "completed"
            message = "Updated successfully." if fetched else "No records were returned."
        results.append(
            {
                "source_name": source,
                "status": status,
                "records_fetched": fetched,
                "records_retained": retained,
                "public_status_message": message,
                "internal_error_message": "; ".join(
                    f"{row['error_type']}: {row['error_message']}" for row in source_errors
                )
                or None,
            }
        )
    return results


def _debug_snapshots_enabled(mode: str) -> bool:
    if "CAREERSIGNAL_WRITE_DEBUG_JSON" in os.environ:
        return bool_env("CAREERSIGNAL_WRITE_DEBUG_JSON", default=False)
    return mode == "local" and bool_env("WRITE_DATA_SNAPSHOTS", default=True)


def _snapshot_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        cleaned = {key: value for key, value in record.items() if key != "_careersignal_category"}
        category = record.get("_careersignal_category")
        if isinstance(category, JobCategoryConfig):
            cleaned["_careersignal_category_name"] = category.category_name
        output.append(cleaned)
    return output


def _records_from_frame(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "where"):
        frame = frame.where(frame.notna(), None)
    return frame.to_dict(orient="records") if hasattr(frame, "to_dict") else []


def _publish_shared(publisher: Any, records: list[dict[str, Any]], run_uuid: str) -> Any:
    if hasattr(publisher, "publish_shared_jobs"):
        return publisher.publish_shared_jobs(records, connector_run_uuid=run_uuid)
    if callable(publisher):
        return publisher(records=records, connector_run_uuid=run_uuid)
    raise TypeError("publisher must be callable or expose publish_shared_jobs")


def run_shared_connector_refresh(
    connector_run_uuid: str | None = None,
    *,
    publisher: Any | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Refresh shared Connector data; never load a user's config snapshot."""

    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    if load_dotenv is not None:
        load_dotenv(root / ".env")
    if connector_run_uuid is None:
        run_uuid = str(uuid4())
    else:
        run_uuid = str(UUID(str(connector_run_uuid)))

    mode = data_mode()
    configs = load_configs(root)
    categories = list(configs.platform_connector.acquisition_categories)
    if not categories:
        raise RuntimeError("platform_connector_config.yml has no acquisition categories")
    connectors = build_connectors(source_names_from_config(configs), root, configs)
    service = MotherDuckService() if _uses_motherduck_analytics(mode) else None
    writer = MotherDuckIngestionWriter(service) if service else None
    if writer:
        init_motherduck_schema(service)
        writer.start_run(run_uuid, mode)

    raw_snapshot_path: Path | None = None
    processed_snapshot_path: Path | None = None
    try:
        with ProgressReporter() as progress:
            raw_records, connector_errors = collect_connector_jobs(
                connectors,
                categories,
                progress,
                retry=configs.platform_connector.retry,
            )

            fetched_count = len(raw_records)
            fetched_records = list(raw_records)
            normalized = normalize_shared_jobs(raw_records, progress)
            raw_records, normalized, freshness_stats = apply_shared_freshness_filter(
                raw_records,
                normalized,
                configs.platform_connector.freshness_filter,
                progress,
            )
            if writer:
                writer.write_raw_jobs(run_uuid, raw_records, progress=progress)
                writer.write_connector_errors(run_uuid, connector_errors)

            deduped = deduplicate_jobs(normalized)
            shared_jobs = enrich_shared_jobs(deduped, progress)
            source_results = _source_results(
                connectors, fetched_records, shared_jobs, connector_errors
            )
            if writer:
                if hasattr(writer, "write_shared_jobs"):
                    writer.write_shared_jobs(run_uuid, shared_jobs, progress=progress)
                else:  # compatibility for older test doubles
                    writer.write_processed_jobs(run_uuid, shared_jobs, progress=progress)

            if _debug_snapshots_enabled(mode):
                raw_snapshot_path = write_json_snapshot(
                    {
                        "metadata": {
                            "connector_run_uuid": run_uuid,
                            "sources": [item.source_name for item in connectors],
                            "freshness_stats": freshness_stats,
                        },
                        "records": _snapshot_records(raw_records),
                    },
                    root / "data" / "raw" / "raw_jobs.json",
                )
                processed_snapshot_path = write_json_snapshot(
                    {
                        "metadata": {
                            "connector_run_uuid": run_uuid,
                            "candidate_independent": True,
                        },
                        "records": shared_jobs,
                    },
                    root / "data" / "processed" / "processed_jobs.json",
                )

        dbt_completed = False
        published_count = 0
        if service and bool_env("CAREERSIGNAL_RUN_DBT", default=True):
            run_shared_dbt_build(dbt_project_dir(), dbt_profiles_dir())
            dbt_completed = True
            if publisher is not None:
                records = _records_from_frame(
                    service.query_df("select * from mart.mart_shared_canonical_jobs")
                )
                _publish_shared(publisher, records, run_uuid)
                published_count = len(records)

        if writer:
            writer.complete_run(
                run_id=run_uuid,
                total_raw_jobs=len(raw_records),
                total_processed_jobs=len(shared_jobs),
                total_deduplicated_jobs=len(deduped),
                total_top_matches=0,
                excel_output_path=None,
            )
        non_successful_sources = [
            item for item in source_results if item["status"] != "completed"
        ]
        if non_successful_sources and len(non_successful_sources) == len(source_results):
            status = "failed"
            public_status_message = "The scheduled refresh was not completed."
        elif non_successful_sources:
            status = "partial"
            public_status_message = "The refresh completed with partial source availability."
        else:
            status = "completed"
            public_status_message = "Updated successfully."
        return {
            "run_id": run_uuid,
            "connector_run_uuid": run_uuid,
            "data_mode": mode,
            "fetched_raw_jobs": fetched_count,
            "raw_jobs": len(raw_records),
            "freshness_filtered_out": freshness_stats["input_jobs"] - freshness_stats["kept_jobs"],
            "freshness_stats": freshness_stats,
            "total_jobs_processed": len(normalized),
            "deduplicated_jobs": len(deduped),
            "shared_jobs": len(shared_jobs),
            "top_matches": 0,
            "dbt_completed": dbt_completed,
            "published_jobs": published_count,
            "status": status,
            "public_status_message": public_status_message,
            "source_results": source_results,
            "excel_exported": False,
            "output_path": None,
            "raw_snapshot_path": raw_snapshot_path,
            "processed_snapshot_path": processed_snapshot_path,
            "jobs": shared_jobs,
        }
    except Exception as exc:
        if writer:
            writer.fail_run(run_uuid, str(exc))
        raise
