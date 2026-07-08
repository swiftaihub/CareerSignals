"""CareerSignal command-line pipeline entry point."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only relevant before dependencies are installed
    load_dotenv = None  # type: ignore[assignment]

from src.config.loader import load_configs
from src.config.schemas import ConfigBundle, JobCategoryConfig
from src.connectors.adzuna_connector import AdzunaConnector
from src.connectors.base import BaseJobConnector
from src.connectors.greenhouse_connector import GreenhouseConnector
from src.connectors.lever_connector import LeverConnector
from src.connectors.mock_connector import MockJobConnector
from src.connectors.serpapi_connector import SerpApiConnector
from src.connectors.usajobs_connector import USAJobsConnector
from src.exporters.excel_exporter import ExcelExporter
from src.ingestion.persistence import write_json_snapshot
from src.processing.date_filter import freshness_decision
from src.processing.deduplicate import deduplicate_jobs
from src.processing.industry_classifier import classify_industry
from src.processing.normalize import normalize_raw_job
from src.processing.scoring import score_job
from src.processing.seniority_classifier import classify_seniority
from src.processing.skill_extractor import RuleBasedSkillExtractor
from src.processing.visa_signal import detect_visa_signal
from src.processing.work_arrangement import detect_work_arrangement
from src.utils.file_outputs import timestamped_output_path
from src.utils.logging import configure_logging
from packages.careersignal_core.dbt.runner import run_dbt, test_dbt
from packages.careersignal_core.settings import (
    bool_env,
    data_mode,
    dbt_profiles_dir,
    dbt_project_dir,
    excel_path,
)
from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema

LOGGER = logging.getLogger(__name__)


def _truthy_env(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def source_names_from_env() -> list[str]:
    """Return requested source names from JOB_SOURCES or legacy JOB_SOURCE."""

    raw_sources = os.getenv("JOB_SOURCES") or os.getenv("JOB_SOURCE") or "mock"
    source_names = [source.strip().casefold() for source in raw_sources.split(",") if source.strip()]
    if "all" in source_names:
        return ["adzuna", "serpapi", "greenhouse", "lever", "usajobs"]
    return source_names or ["mock"]


def build_connector(
    source_name: str,
    project_root: Path,
    configs: ConfigBundle,
) -> BaseJobConnector:
    """Create the configured job connector."""

    normalized = source_name.casefold().strip()
    if normalized == "adzuna":
        return AdzunaConnector(global_filters=configs.jobs.global_filters)
    if normalized in {"serpapi", "serpapi_google_jobs", "google_jobs"}:
        return SerpApiConnector(global_filters=configs.jobs.global_filters)
    if normalized == "greenhouse":
        return GreenhouseConnector(global_filters=configs.jobs.global_filters)
    if normalized == "lever":
        return LeverConnector(global_filters=configs.jobs.global_filters)
    if normalized in {"usajobs", "usa_jobs"}:
        return USAJobsConnector(global_filters=configs.jobs.global_filters)
    return MockJobConnector(project_root / "data" / "sample" / "sample_jobs.json")


def build_connectors(
    source_names: list[str],
    project_root: Path,
    configs: ConfigBundle,
) -> list[BaseJobConnector]:
    return [build_connector(source_name, project_root, configs) for source_name in source_names]


def _collect_jobs(
    connectors: list[BaseJobConnector],
    categories: list[JobCategoryConfig],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_records: list[dict[str, Any]] = []
    connector_errors: list[dict[str, Any]] = []
    for connector in connectors:
        for category in categories:
            try:
                fetched = connector.fetch_jobs(category)
            except Exception as exc:
                LOGGER.exception(
                    "Connector %s failed for category %s.",
                    connector.source_name,
                    category.category_name,
                )
                connector_errors.append(
                    {
                        "source": connector.source_name,
                        "category_name": category.category_name,
                        "query_title": ", ".join(category.search_titles),
                        "error_message": str(exc),
                        "error_type": type(exc).__name__,
                    }
                )
                continue
            raw_records.extend(
                {
                    **record,
                    "_careersignal_category": category,
                    "_careersignal_source": connector.source_name,
                }
                for record in fetched
            )
    return raw_records, connector_errors


def _normalize_jobs(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_jobs: list[dict[str, Any]] = []
    for record in raw_records:
        category = record["_careersignal_category"]
        normalized_jobs.append(normalize_raw_job(record, category))
    return normalized_jobs


def _apply_freshness_filter(
    raw_records: list[dict[str, Any]],
    normalized_jobs: list[dict[str, Any]],
    configs: ConfigBundle,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    freshness_filter = configs.jobs.freshness_filter
    stats = {
        "input_jobs": len(normalized_jobs),
        "kept_jobs": 0,
        "older_than_max_age": 0,
        "unknown_date_excluded": 0,
        "unknown_date_included": 0,
        "disabled": 0,
    }

    if not freshness_filter.enabled:
        stats["kept_jobs"] = len(normalized_jobs)
        stats["disabled"] = len(normalized_jobs)
        return raw_records, normalized_jobs, stats

    kept_raw_records: list[dict[str, Any]] = []
    kept_normalized_jobs: list[dict[str, Any]] = []

    for raw_record, normalized_job in zip(raw_records, normalized_jobs):
        decision = freshness_decision(normalized_job, freshness_filter)
        stats[decision.reason] = stats.get(decision.reason, 0) + 1
        if decision.keep:
            kept_raw_records.append(raw_record)
            kept_normalized_jobs.append(normalized_job)

    stats["kept_jobs"] = len(kept_normalized_jobs)
    filtered_out = stats["input_jobs"] - stats["kept_jobs"]
    if filtered_out:
        LOGGER.info(
            "Freshness filter kept %s of %s jobs posted within %s hours.",
            stats["kept_jobs"],
            stats["input_jobs"],
            freshness_filter.max_post_age_hours,
        )

    return kept_raw_records, kept_normalized_jobs, stats


def _enrich_and_score_jobs(
    jobs: list[dict[str, Any]],
    configs: ConfigBundle,
) -> list[dict[str, Any]]:
    candidate = configs.candidate_profile.candidate
    extractor = RuleBasedSkillExtractor(candidate, configs.skill_taxonomy)
    categories_by_name = {
        category.category_name: category for category in configs.jobs.job_categories
    }

    processed_jobs: list[dict[str, Any]] = []
    for job in jobs:
        category = categories_by_name[job["category_name"]]
        description = str(job.get("job_description") or "")

        skill_result = extractor.extract(description)
        enriched = {
            **job,
            "industry": classify_industry(
                category_config=category,
                company=str(job.get("company") or ""),
                description=description,
                raw_industry=str(job.get("industry") or ""),
            ),
            "seniority": classify_seniority(
                str(job.get("job_title") or ""),
                description,
            ),
            "work_arrangement": detect_work_arrangement(
                str(job.get("job_title") or ""),
                str(job.get("location") or ""),
                description,
            ),
            "visa_signal": detect_visa_signal(
                description,
                candidate.visa_keywords,
            ),
            "required_skills": skill_result.required_skills,
            "preferred_skills": skill_result.preferred_skills,
            "all_extracted_skills": skill_result.all_extracted_skills,
        }
        processed_jobs.append(
            score_job(
                enriched,
                candidate,
                category,
                configs.jobs.ranking_weights,
            )
        )

    return sorted(
        processed_jobs,
        key=lambda item: (
            float(item.get("match_score") or 0),
            float(item.get("salary_midpoint") or 0),
            str(item.get("date_posted") or ""),
        ),
        reverse=True,
    )


def _snapshot_ready_raw_records(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    serializable: list[dict[str, Any]] = []
    for record in raw_records:
        category = record.get("_careersignal_category")
        cleaned = {key: value for key, value in record.items() if key != "_careersignal_category"}
        if isinstance(category, JobCategoryConfig):
            cleaned["_careersignal_category_name"] = category.category_name
        serializable.append(cleaned)
    return serializable


def _resolved_project_path(root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    root_candidate = (root / path).resolve()
    if root_candidate.exists():
        return root_candidate
    api_candidate = (root / "apps" / "api" / path).resolve()
    if api_candidate.exists():
        return api_candidate
    return root_candidate


def _debug_json_enabled(current_data_mode: str) -> bool:
    if "CAREERSIGNAL_WRITE_DEBUG_JSON" in os.environ:
        return bool_env("CAREERSIGNAL_WRITE_DEBUG_JSON", default=False)
    if "WRITE_DATA_SNAPSHOTS" in os.environ:
        return _truthy_env("WRITE_DATA_SNAPSHOTS", default=False)
    return current_data_mode == "local"


def _run_dbt_if_enabled(root: Path) -> bool:
    project_dir = _resolved_project_path(root, dbt_project_dir())
    profiles_dir = _resolved_project_path(root, dbt_profiles_dir())
    ran_dbt = False
    if bool_env("CAREERSIGNAL_RUN_DBT", default=True):
        LOGGER.info("Running dbt models.")
        run_dbt(project_dir, profiles_dir)
        ran_dbt = True
    if bool_env("CAREERSIGNAL_RUN_DBT_TESTS", default=True):
        LOGGER.info("Running dbt tests.")
        test_dbt(project_dir, profiles_dir)
    return ran_dbt


def _mart_dataframes(service: MotherDuckService) -> dict[str, Any]:
    return {
        "All Jobs": service.query_df("select * from mart.mart_jobs_scored order by match_score desc"),
        "Top Matches": service.query_df("select * from mart.mart_top_matches"),
        "By Category Summary": service.query_df("select * from mart.mart_category_summary"),
        "Skill Gap Analysis": service.query_df("select * from mart.mart_skill_gap_analysis"),
        "Company Priority List": service.query_df("select * from mart.mart_company_priority_list"),
    }


def export_excel_from_current_data(project_root: str | Path = ".") -> Path:
    """Export Excel from the current source of truth for the active data mode."""

    root = Path(project_root).resolve()
    if load_dotenv is not None:
        load_dotenv(root / ".env")

    configs = load_configs(root)
    output_path = timestamped_output_path(_resolved_project_path(root, excel_path()))
    exporter = ExcelExporter(configs.candidate_profile.candidate, configs.skill_taxonomy)

    if data_mode() == "motherduck":
        exporter.export_dataframes(_mart_dataframes(MotherDuckService()), output_path)
        return output_path

    summary = run_pipeline(root)
    return Path(summary["output_path"])


def run_pipeline(project_root: str | Path = ".") -> dict[str, Any]:
    """Run the full CareerSignal MVP pipeline."""

    root = Path(project_root).resolve()
    if load_dotenv is not None:
        load_dotenv(root / ".env")

    current_data_mode = data_mode()
    run_id = uuid4().hex
    configs = load_configs(root)
    source_names = source_names_from_env()
    connectors = build_connectors(source_names, root, configs)
    md_service = MotherDuckService() if current_data_mode == "motherduck" else None
    md_writer = MotherDuckIngestionWriter(md_service) if md_service else None

    if md_writer:
        LOGGER.info("Initializing MotherDuck schemas.")
        init_motherduck_schema(md_service)
        md_writer.start_run(run_id, current_data_mode)

    output_path = timestamped_output_path(_resolved_project_path(root, excel_path()))

    try:
        raw_records, connector_errors = _collect_jobs(connectors, configs.jobs.job_categories)
        if not raw_records and not any(connector.source_name == "mock" for connector in connectors):
            LOGGER.warning("No jobs returned from configured sources; falling back to mock connector.")
            connectors = [build_connector("mock", root, configs)]
            raw_records, fallback_errors = _collect_jobs(connectors, configs.jobs.job_categories)
            connector_errors.extend(fallback_errors)

        fetched_raw_record_count = len(raw_records)
        normalized_jobs = _normalize_jobs(raw_records)

        if md_writer:
            LOGGER.info("Writing raw connector observations to MotherDuck.")
            md_writer.write_raw_jobs(run_id, raw_records)
            md_writer.write_connector_errors(run_id, connector_errors)
            md_writer.write_candidate_skills(configs.candidate_profile.candidate)

        raw_records, normalized_jobs, freshness_stats = _apply_freshness_filter(
            raw_records,
            normalized_jobs,
            configs,
        )

        raw_snapshot_path = None
        if _debug_json_enabled(current_data_mode):
            raw_snapshot_path = write_json_snapshot(
                {
                    "metadata": {
                        "run_id": run_id,
                        "data_mode": current_data_mode,
                        "sources": [connector.source_name for connector in connectors],
                        "fetched_raw_record_count": fetched_raw_record_count,
                        "raw_record_count": len(raw_records),
                        "freshness_filter": configs.jobs.freshness_filter.model_dump()
                        if hasattr(configs.jobs.freshness_filter, "model_dump")
                        else configs.jobs.freshness_filter.dict(),
                        "freshness_stats": freshness_stats,
                    },
                    "records": _snapshot_ready_raw_records(raw_records),
                },
                root / "data" / "raw" / "raw_jobs.json",
            )

        deduped_jobs = deduplicate_jobs(normalized_jobs)
        processed_jobs = _enrich_and_score_jobs(deduped_jobs, configs)

        if md_writer:
            LOGGER.info("Writing processed bridge rows to MotherDuck.")
            md_writer.write_processed_jobs(run_id, processed_jobs)

        processed_snapshot_path = None
        if _debug_json_enabled(current_data_mode):
            processed_snapshot_path = write_json_snapshot(
                {
                    "metadata": {
                        "run_id": run_id,
                        "data_mode": current_data_mode,
                        "sources": [connector.source_name for connector in connectors],
                        "processed_record_count": len(processed_jobs),
                        "freshness_filter": configs.jobs.freshness_filter.model_dump()
                        if hasattr(configs.jobs.freshness_filter, "model_dump")
                        else configs.jobs.freshness_filter.dict(),
                        "freshness_stats": freshness_stats,
                    },
                    "records": processed_jobs,
                },
                root / "data" / "processed" / "processed_jobs.json",
            )

        if current_data_mode == "motherduck" and md_service:
            ran_dbt = _run_dbt_if_enabled(root)
            if ran_dbt:
                LOGGER.info("Exporting Excel workbook from MotherDuck mart tables.")
                ExcelExporter(
                    configs.candidate_profile.candidate,
                    configs.skill_taxonomy,
                ).export_dataframes(_mart_dataframes(md_service), output_path)
            else:
                LOGGER.warning(
                    "dbt execution is disabled; exporting Excel from processed Python rows."
                )
                ExcelExporter(
                    configs.candidate_profile.candidate,
                    configs.skill_taxonomy,
                ).export(
                    processed_jobs,
                    output_path,
                    configs.jobs.output.top_match_threshold,
                )
        else:
            ExcelExporter(
                configs.candidate_profile.candidate,
                configs.skill_taxonomy,
            ).export(
                processed_jobs,
                output_path,
                configs.jobs.output.top_match_threshold,
            )

        top_matches = [
            job
            for job in processed_jobs
            if float(job.get("match_score") or 0) >= configs.jobs.output.top_match_threshold
        ]

        if md_writer:
            md_writer.complete_run(
                run_id=run_id,
                total_raw_jobs=fetched_raw_record_count,
                total_processed_jobs=len(processed_jobs),
                total_deduplicated_jobs=len(deduped_jobs),
                total_top_matches=len(top_matches),
                excel_output_path=str(output_path),
            )

        return {
            "run_id": run_id,
            "data_mode": current_data_mode,
            "raw_jobs": len(raw_records),
            "fetched_raw_jobs": fetched_raw_record_count,
            "freshness_filtered_out": freshness_stats["input_jobs"] - freshness_stats["kept_jobs"],
            "freshness_stats": freshness_stats,
            "total_jobs_processed": len(normalized_jobs),
            "deduplicated_jobs": len(deduped_jobs),
            "top_matches": len(top_matches),
            "output_path": output_path,
            "raw_snapshot_path": raw_snapshot_path,
            "processed_snapshot_path": processed_snapshot_path,
            "jobs": processed_jobs,
        }
    except Exception as exc:
        if md_writer:
            md_writer.fail_run(run_id, str(exc))
        raise


def main() -> None:
    configure_logging()
    project_root = Path(__file__).resolve().parents[1]
    summary = run_pipeline(project_root)

    print("CareerSignal pipeline completed.")
    print(f"Fetched jobs: {summary['fetched_raw_jobs']}")
    print(f"Freshness filtered out: {summary['freshness_filtered_out']}")
    print(f"Total jobs processed: {summary['total_jobs_processed']}")
    print(f"Deduplicated jobs: {summary['deduplicated_jobs']}")
    print(f"Top matches: {summary['top_matches']}")
    print(f"Excel exported to: {Path(summary['output_path']).relative_to(project_root)}")
    if summary.get("raw_snapshot_path"):
        print(f"Raw snapshot: {Path(summary['raw_snapshot_path']).relative_to(project_root)}")
    if summary.get("processed_snapshot_path"):
        print(
            "Processed snapshot: "
            f"{Path(summary['processed_snapshot_path']).relative_to(project_root)}"
        )


if __name__ == "__main__":
    main()
