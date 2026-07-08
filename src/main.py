"""CareerSignal command-line pipeline entry point."""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
from typing import Any

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
) -> list[dict[str, Any]]:
    raw_records: list[dict[str, Any]] = []
    for connector in connectors:
        for category in categories:
            try:
                fetched = connector.fetch_jobs(category)
            except Exception:
                LOGGER.exception(
                    "Connector %s failed for category %s.",
                    connector.source_name,
                    category.category_name,
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
    return raw_records


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


def run_pipeline(project_root: str | Path = ".") -> dict[str, Any]:
    """Run the full CareerSignal MVP pipeline."""

    root = Path(project_root).resolve()
    if load_dotenv is not None:
        load_dotenv(root / ".env")

    configs = load_configs(root)
    source_names = source_names_from_env()
    connectors = build_connectors(source_names, root, configs)

    raw_records = _collect_jobs(connectors, configs.jobs.job_categories)
    if not raw_records and not any(connector.source_name == "mock" for connector in connectors):
        LOGGER.warning("No jobs returned from configured sources; falling back to mock connector.")
        connectors = [build_connector("mock", root, configs)]
        raw_records = _collect_jobs(connectors, configs.jobs.job_categories)

    fetched_raw_record_count = len(raw_records)
    normalized_jobs = _normalize_jobs(raw_records)
    raw_records, normalized_jobs, freshness_stats = _apply_freshness_filter(
        raw_records,
        normalized_jobs,
        configs,
    )

    raw_snapshot_path = None
    if _truthy_env("WRITE_DATA_SNAPSHOTS", default=True):
        raw_snapshot_path = write_json_snapshot(
            {
                "metadata": {
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

    processed_snapshot_path = None
    if _truthy_env("WRITE_DATA_SNAPSHOTS", default=True):
        processed_snapshot_path = write_json_snapshot(
            {
                "metadata": {
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

    output_path = timestamped_output_path(root / configs.jobs.output.excel_file)
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

    return {
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
