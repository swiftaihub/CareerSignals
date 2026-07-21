"""Trusted system-only Connector refresh for the shared job universe."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from typing import Any, Iterable
from uuid import UUID, uuid4

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from packages.careersignal_core.dbt.runner import run_shared_dbt_build
from packages.careersignal_core.settings import (
    bool_env,
    data_mode,
    dbt_profiles_dir,
    dbt_project_dir,
    saas_mode,
)
from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.loader import load_configs
from src.config.schemas import ConfigBundle, ConnectorRetryConfig, GlobalFilters, JobCategoryConfig
from packages.careersignal_core.repositories.bootstrap import (
    acquisition_config_from_snapshot,
    stable_hash,
)
from src.config.loader import effective_config_hash
from src.connectors.adzuna_connector import AdzunaConnector
from src.connectors.base import BaseJobConnector
from src.connectors.greenhouse_connector import GreenhouseConnector
from src.connectors.lever_connector import LeverConnector
from src.connectors.mock_connector import MockJobConnector
from src.connectors.serpapi_connector import SerpApiConnector
from src.connectors.usajobs_connector import USAJobsConnector
from src.connectors.http_utils import env_int, limited_search_pairs
from src.ingestion.persistence import write_json_snapshot
from src.pipelines.shared_processing import (
    apply_shared_freshness_filter,
    enrich_shared_jobs,
    normalize_shared_jobs,
)
from src.processing.deduplicate import deduplicate_jobs
from src.utils.progress import ProgressReporter

LOGGER = logging.getLogger(__name__)


class SharedConnectorRefreshError(RuntimeError):
    """Raised with a credential-safe summary at the pipeline boundary."""


def _safe_failure_summary(exc: BaseException, message: str) -> str:
    """Describe a failure without including exception-controlled text."""

    return f"{type(exc).__name__}: {message}"


def _uses_motherduck_analytics(mode: str) -> bool:
    """Return whether the shared bridge must feed the MotherDuck dbt target.

    In SaaS, ``CAREERSIGNAL_DATA_MODE=postgres`` describes the serving layer,
    while dbt still runs against MotherDuck. Treating it as a mutually
    exclusive storage choice silently discarded every shared refresh.
    """

    if mode == "motherduck":
        return True
    target = os.getenv("DBT_TARGET", "").strip().casefold()
    return target in {"dev", "prod"} and bool(os.getenv("MOTHERDUCK_TOKEN", "").strip())


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


def _active_user_snapshots() -> list[dict[str, Any]]:
    from packages.careersignal_core.repositories.configs import ConfigRepository

    return ConfigRepository().active_user_snapshots()


def _dedupe_strings(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def _user_jobs_documents(user_snapshots: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for snapshot in user_snapshots:
        configs = snapshot.get("configs")
        if not isinstance(configs, dict):
            continue
        jobs_config = configs.get("jobs_config")
        if isinstance(jobs_config, dict):
            documents.append(jobs_config)
    return documents


def _aggregate_global_filters(
    platform_filters: GlobalFilters,
    user_jobs_documents: list[dict[str, Any]],
) -> GlobalFilters:
    if not user_jobs_documents:
        return platform_filters

    raw_filters = [document.get("global_filters") or {} for document in user_jobs_documents]
    countries = _dedupe_strings(filter_config.get("country") for filter_config in raw_filters)

    def combined_list(field: str) -> list[str]:
        lists = [filter_config.get(field) for filter_config in raw_filters]
        # An empty user filter means that user is open to all values; the shared
        # acquisition query must not exclude their possible matches.
        if any(not value for value in lists):
            return []
        return _dedupe_strings(item for value in lists for item in value)

    return GlobalFilters(
        country=countries[0] if len(countries) == 1 else platform_filters.country,
        locations=combined_list("locations"),
        work_type=combined_list("work_type"),
        employment_type=combined_list("employment_type"),
    )


def _aggregate_acquisition_categories(
    configs: ConfigBundle,
    user_jobs_documents: list[dict[str, Any]],
) -> list[JobCategoryConfig]:
    raw_categories: list[dict[str, Any]] = []
    for document in user_jobs_documents:
        categories = document.get("job_categories") or []
        if isinstance(categories, list):
            raw_categories.extend(category for category in categories if isinstance(category, dict))

    if not raw_categories:
        return list(configs.platform_connector.acquisition_categories)

    categories: list[JobCategoryConfig] = []
    seen: set[str] = set()
    for raw in raw_categories:
        category = JobCategoryConfig.model_validate(raw)
        key = category.model_dump_json()
        if key in seen:
            continue
        seen.add(key)
        categories.append(category)
    return categories


def _config_hashes(snapshot: dict[str, Any]) -> dict[str, str]:
    configs = snapshot.get("configs") if isinstance(snapshot, dict) else {}
    if not isinstance(configs, dict):
        return {}
    return {
        str(config_type): effective_config_hash(config)
        for config_type, config in configs.items()
        if isinstance(config, dict)
    }


def _auditable_user_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    acquisition_config = acquisition_config_from_snapshot(snapshot)
    return {
        "user_uuid": str(snapshot.get("user_uuid")),
        "config_revisions": dict(snapshot.get("config_revision_map") or {}),
        "effective_config_hashes": _config_hashes(snapshot),
        "acquisition_config": acquisition_config,
        "acquisition_hash": stable_hash(acquisition_config),
    }


def build_acquisition_query_plan(
    *,
    source_names: list[str],
    configs: ConfigBundle,
    global_filters: GlobalFilters,
    categories: list[JobCategoryConfig],
    user_snapshots: Iterable[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Return a deterministic, deduplicated connector query plan.

    Request payloads intentionally contain acquisition fields only. Candidate
    profile, skill weights, resumes, and other personal ranking fields are not
    present in this structure and are never sent to external job APIs.
    """

    snapshots = list(user_snapshots or [])
    per_user_category_keys: dict[str, set[str]] = {}
    for snapshot in snapshots:
        user_uuid = str(snapshot.get("user_uuid"))
        configs_map = snapshot.get("configs")
        jobs_config = configs_map.get("jobs_config") if isinstance(configs_map, dict) else {}
        raw_categories = jobs_config.get("job_categories") if isinstance(jobs_config, dict) else []
        keys: set[str] = set()
        if isinstance(raw_categories, list):
            for raw in raw_categories:
                if isinstance(raw, dict):
                    keys.add(JobCategoryConfig.model_validate(raw).model_dump_json())
        per_user_category_keys[user_uuid] = keys

    queries: dict[str, dict[str, Any]] = {}
    for source_name in source_names:
        normalized_source = source_name.casefold().strip()
        budget = configs.platform_connector.source_budgets.get(normalized_source)
        max_queries = budget.query_limit_per_category if budget is not None else 4
        for category in categories:
            category_key = category.model_dump_json()
            interested_users = {
                user_uuid
                for user_uuid, keys in per_user_category_keys.items()
                if category_key in keys
            }
            interested_count = len(interested_users) if interested_users else max(1, len(snapshots))
            for title, location in limited_search_pairs(category, global_filters, max_queries):
                request_json = {
                    "source_name": normalized_source,
                    "query_title": title,
                    "category_name": category.category_name,
                    "location": location,
                    "country": global_filters.country,
                    "industries": list(category.industries),
                    "seniority": list(category.seniority),
                    "work_type": list(global_filters.work_type),
                    "employment_type": list(global_filters.employment_type),
                }
                query_key = stable_hash(request_json)
                current = queries.setdefault(
                    query_key,
                    {
                        "query_key": query_key,
                        "source_name": normalized_source,
                        "request_json": request_json,
                        "interested_user_count": 0,
                        "status": "planned",
                        "records_fetched": 0,
                    },
                )
                current["interested_user_count"] = max(
                    int(current["interested_user_count"]),
                    interested_count,
                )
    return [queries[key] for key in sorted(queries)]


def build_acquisition_inputs(
    configs: ConfigBundle,
    user_snapshots: Iterable[dict[str, Any]] | None,
) -> tuple[GlobalFilters, list[JobCategoryConfig], dict[str, Any]]:
    """Build shared acquisition inputs from all active users when available."""

    snapshots = list(user_snapshots or [])
    user_jobs = _user_jobs_documents(snapshots)
    filters = _aggregate_global_filters(configs.platform_connector.global_filters, user_jobs)
    categories = _aggregate_acquisition_categories(configs, user_jobs)
    return (
        filters,
        categories,
        {
            "active_user_count": len(snapshots),
            "user_config_driven": bool(user_jobs),
            "acquisition_category_count": len(categories),
            "user_snapshots": [_auditable_user_snapshot(snapshot) for snapshot in snapshots],
        },
    )


def build_connector(
    source_name: str,
    project_root: Path,
    configs: ConfigBundle,
    global_filters: GlobalFilters | None = None,
) -> BaseJobConnector:
    normalized = source_name.casefold().strip()
    filters = global_filters or configs.platform_connector.global_filters
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
    source_names: list[str],
    project_root: Path,
    configs: ConfigBundle,
    global_filters: GlobalFilters | None = None,
) -> list[BaseJobConnector]:
    return [build_connector(name, project_root, configs, global_filters) for name in source_names]


def collect_connector_jobs(
    connectors: list[BaseJobConnector],
    categories: list[JobCategoryConfig],
    progress: ProgressReporter | None = None,
    retry: ConnectorRetryConfig | None = None,
    max_source_concurrency: int = 5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    policy = retry or ConnectorRetryConfig(max_attempts=1, backoff_seconds=0)

    def collect_source(
        connector: BaseJobConnector,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        started_at = time.monotonic()
        LOGGER.info(
            "Connector %s started (categories=%s)",
            connector.source_name,
            len(categories),
        )
        source_records: list[dict[str, Any]] = []
        source_errors: list[dict[str, Any]] = []
        for category in categories:
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
                    LOGGER.error(
                        "Connector %s failed for category %s (%s)",
                        connector.source_name,
                        category.category_name,
                        type(exc).__name__,
                    )
                    source_errors.append(
                        {
                            "source": connector.source_name,
                            "category_name": category.category_name,
                            "query_title": ", ".join(category.search_titles),
                            "error_message": "Connector request failed.",
                            "error_type": type(exc).__name__,
                        }
                    )
            if fetched is None:
                continue
            source_records.extend(
                {
                    **record,
                    "_careersignal_category": category,
                    "_careersignal_source": connector.source_name,
                }
                for record in fetched
            )
        elapsed_seconds = time.monotonic() - started_at
        LOGGER.info(
            "Connector %s completed (records=%s, errors=%s, elapsed_seconds=%.1f)",
            connector.source_name,
            len(source_records),
            len(source_errors),
            elapsed_seconds,
        )
        return source_records, source_errors

    worker_count = min(max(1, max_source_concurrency), len(connectors))
    if worker_count <= 1:
        source_results = [collect_source(connector) for connector in connectors]
    else:
        LOGGER.info(
            "Fetching %s connector sources with concurrency %s",
            len(connectors),
            worker_count,
        )
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="connector-source",
        ) as executor:
            futures = [executor.submit(collect_source, connector) for connector in connectors]
            # Resolve in connector order so snapshots and diagnostics remain deterministic.
            source_results = [future.result() for future in futures]

    raw_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source_records, source_errors in source_results:
        raw_records.extend(source_records)
        errors.extend(source_errors)
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
    user_snapshots: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refresh shared Connector data from all active users' acquisition inputs."""

    root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    if load_dotenv is not None:
        load_dotenv(root / ".env")
    if connector_run_uuid is None:
        run_uuid = str(uuid4())
    else:
        run_uuid = str(UUID(str(connector_run_uuid)))

    mode = data_mode()
    configs = load_configs(root)
    if user_snapshots is None and saas_mode() and mode == "postgres":
        user_snapshots = _active_user_snapshots()
    else:
        user_snapshots = list(user_snapshots or [])
    acquisition_filters, categories, acquisition_metadata = build_acquisition_inputs(
        configs, user_snapshots
    )
    if not categories:
        raise RuntimeError("No acquisition categories are available for shared refresh")
    source_names = source_names_from_config(configs)
    acquisition_metadata["queries"] = build_acquisition_query_plan(
        source_names=source_names,
        configs=configs,
        global_filters=acquisition_filters,
        categories=categories,
        user_snapshots=user_snapshots,
    )
    connectors = build_connectors(source_names, root, configs, acquisition_filters)
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
                max_source_concurrency=min(
                    env_int("CONNECTOR_SOURCE_MAX_CONCURRENCY", 5),
                    10,
                ),
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
                            "acquisition": acquisition_metadata,
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
            "acquisition": acquisition_metadata,
            "excel_exported": False,
            "output_path": None,
            "raw_snapshot_path": raw_snapshot_path,
            "processed_snapshot_path": processed_snapshot_path,
            "jobs": shared_jobs,
        }
    except Exception as exc:
        failure_summary = _safe_failure_summary(exc, "Shared connector refresh failed.")
        if writer:
            try:
                writer.fail_run(run_uuid, failure_summary)
            except Exception as record_exc:
                LOGGER.error(
                    "Unable to record shared connector refresh failure (%s)",
                    type(record_exc).__name__,
                )
        raise SharedConnectorRefreshError(failure_summary) from None
