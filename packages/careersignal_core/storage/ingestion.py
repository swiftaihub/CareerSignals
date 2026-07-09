"""MotherDuck ingestion writers for raw and processed CareerSignal data."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any

from packages.careersignal_core.storage.motherduck import MotherDuckService
from src.config.schemas import Candidate, JobCategoryConfig
from src.utils.hashing import stable_hash
from src.utils.progress import ProgressReporter
from src.utils.text_cleaning import clean_text


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=_json_default)


def _raw_payload(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if not key.startswith("_careersignal_") and key != "raw_source_record"
    } | {
        "raw_source_record": record.get("raw_source_record")
    }


def _raw_job_key(record: dict[str, Any]) -> str:
    return clean_text(
        record.get("external_id")
        or record.get("job_id")
        or record.get("id")
        or record.get("jd_post_link")
        or record.get("url")
        or record.get("title")
        or record.get("job_title")
    )


def _batch_size() -> int:
    raw_value = os.getenv("CAREERSIGNAL_MOTHERDUCK_BATCH_SIZE", "1000")
    try:
        return max(int(raw_value), 1)
    except ValueError:
        return 1000


class MotherDuckIngestionWriter:
    """Writes pipeline observations and bridge data into MotherDuck."""

    def __init__(self, service: MotherDuckService | None = None) -> None:
        self.service = service or MotherDuckService()

    def start_run(self, run_id: str, data_mode: str) -> None:
        with self.service.connect() as conn:
            conn.execute(
                """
                insert or replace into raw.ingestion_runs (
                    run_id,
                    run_started_at,
                    run_completed_at,
                    status,
                    data_mode,
                    total_raw_jobs,
                    total_processed_jobs,
                    total_deduplicated_jobs,
                    total_top_matches,
                    excel_output_path,
                    error_message
                )
                values (?, ?, null, 'running', ?, 0, 0, 0, 0, null, null)
                """,
                [run_id, _now(), data_mode],
            )

    def complete_run(
        self,
        *,
        run_id: str,
        total_raw_jobs: int,
        total_processed_jobs: int,
        total_deduplicated_jobs: int,
        total_top_matches: int,
        excel_output_path: str | None,
    ) -> None:
        with self.service.connect() as conn:
            conn.execute(
                """
                update raw.ingestion_runs
                set
                    run_completed_at = ?,
                    status = 'completed',
                    total_raw_jobs = ?,
                    total_processed_jobs = ?,
                    total_deduplicated_jobs = ?,
                    total_top_matches = ?,
                    excel_output_path = ?,
                    error_message = null
                where run_id = ?
                """,
                [
                    _now(),
                    total_raw_jobs,
                    total_processed_jobs,
                    total_deduplicated_jobs,
                    total_top_matches,
                    excel_output_path,
                    run_id,
                ],
            )

    def fail_run(self, run_id: str, error_message: str) -> None:
        with self.service.connect() as conn:
            conn.execute(
                """
                update raw.ingestion_runs
                set run_completed_at = ?, status = 'failed', error_message = ?
                where run_id = ?
                """,
                [_now(), error_message[:2000], run_id],
            )

    def _raw_job_row(
        self,
        run_id: str,
        record: dict[str, Any],
        fetched_at: datetime,
    ) -> tuple[Any, ...]:
        category = record.get("_careersignal_category")
        category_name = (
            category.category_name
            if isinstance(category, JobCategoryConfig)
            else clean_text(record.get("category_name"))
        )
        query_title = ", ".join(category.search_titles) if isinstance(category, JobCategoryConfig) else None
        payload = _raw_payload(record)
        payload_json = canonical_json(payload)
        payload_hash = stable_hash(payload_json, length=32)
        raw_job_key = _raw_job_key(record)
        raw_record_id = stable_hash(
            run_id,
            record.get("_careersignal_source"),
            raw_job_key,
            payload_hash,
            length=32,
        )
        source_url = clean_text(record.get("jd_post_link") or record.get("url") or record.get("apply_link"))

        return (
            raw_record_id,
            run_id,
            clean_text(record.get("_careersignal_source") or record.get("source")),
            category_name,
            query_title,
            None,
            raw_job_key,
            payload_json,
            payload_hash,
            fetched_at,
            source_url,
            "success",
        )

    def write_raw_jobs(
        self,
        run_id: str,
        raw_records: list[dict[str, Any]],
        progress: ProgressReporter | None = None,
    ) -> int:
        fetched_at = _now()
        total_records = len(raw_records)
        if not total_records:
            return 0

        batch_size = _batch_size()
        inserted_count = 0
        batch: list[tuple[Any, ...]] = []
        records_iterable = (
            progress.iter(
                raw_records,
                "Preparing and writing raw MotherDuck rows",
                total=total_records,
            )
            if progress
            else raw_records
        )
        with self.service.connect() as conn:
            for record in records_iterable:
                batch.append(self._raw_job_row(run_id, record, fetched_at))
                if len(batch) >= batch_size:
                    self._insert_raw_job_batch(conn, batch)
                    inserted_count += len(batch)
                    batch.clear()
            if batch:
                self._insert_raw_job_batch(conn, batch)
                inserted_count += len(batch)
        return inserted_count

    def _insert_raw_job_batch(self, conn: Any, rows: list[tuple[Any, ...]]) -> None:
        conn.executemany(
            """
            insert or ignore into raw.job_posts_raw (
                raw_record_id,
                run_id,
                source,
                category_name,
                query_title,
                query_location,
                raw_job_key,
                raw_payload,
                raw_payload_hash,
                fetched_at,
                source_url,
                connector_status
            )
            values (?, ?, ?, ?, ?, ?, ?, cast(? as json), ?, ?, ?, ?)
            """,
            rows,
        )

    def write_connector_errors(
        self,
        run_id: str,
        errors: list[dict[str, Any]],
    ) -> int:
        rows = [
            (
                stable_hash(run_id, error.get("source"), error.get("category_name"), error.get("error_message"), length=32),
                run_id,
                clean_text(error.get("source")),
                clean_text(error.get("category_name")),
                clean_text(error.get("query_title")),
                clean_text(error.get("error_message")),
                clean_text(error.get("error_type")),
                _now(),
            )
            for error in errors
        ]
        if not rows:
            return 0

        with self.service.connect() as conn:
            conn.executemany(
                """
                insert or ignore into raw.connector_errors (
                    error_id,
                    run_id,
                    source,
                    category_name,
                    query_title,
                    error_message,
                    error_type,
                    occurred_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def write_processed_jobs(
        self,
        run_id: str,
        jobs: list[dict[str, Any]],
        progress: ProgressReporter | None = None,
    ) -> int:
        inserted_at = _now()
        rows: list[tuple[Any, ...]] = []
        jobs_iterable = (
            progress.iter(jobs, "Preparing processed MotherDuck rows", total=len(jobs))
            if progress
            else jobs
        )
        for job in jobs_iterable:
            rows.append(
                (
                    job.get("job_id"),
                    run_id,
                    job.get("source"),
                    job.get("category_name"),
                    job.get("job_title"),
                    job.get("normalized_title"),
                    job.get("company"),
                    job.get("industry"),
                    job.get("location"),
                    job.get("work_arrangement"),
                    job.get("employment_type"),
                    job.get("seniority"),
                    job.get("salary_min"),
                    job.get("salary_max"),
                    job.get("salary_midpoint"),
                    job.get("salary_range_text"),
                    job.get("date_posted"),
                    job.get("date_collected"),
                    job.get("jd_post_link"),
                    job.get("apply_link"),
                    job.get("job_description"),
                    canonical_json(job.get("required_skills") or []),
                    canonical_json(job.get("preferred_skills") or []),
                    canonical_json(job.get("all_extracted_skills") or []),
                    job.get("visa_signal"),
                    job.get("match_score"),
                    job.get("match_tier"),
                    job.get("reasoning_summary"),
                    inserted_at,
                )
            )

        if not rows:
            return 0

        batch_size = _batch_size()
        inserted_count = 0
        with self.service.connect() as conn:
            for index in range(0, len(rows), batch_size):
                batch = rows[index : index + batch_size]
                self._insert_processed_job_batch(conn, batch)
                inserted_count += len(batch)
        return inserted_count

    def _insert_processed_job_batch(self, conn: Any, rows: list[tuple[Any, ...]]) -> None:
        conn.executemany(
            """
            insert into staging.python_jobs_processed (
                job_id,
                run_id,
                source,
                category_name,
                job_title,
                normalized_title,
                company,
                industry,
                location,
                work_arrangement,
                employment_type,
                seniority,
                salary_min,
                salary_max,
                salary_midpoint,
                salary_range_text,
                date_posted,
                date_collected,
                jd_post_link,
                apply_link,
                job_description,
                required_skills,
                preferred_skills,
                all_extracted_skills,
                visa_signal,
                match_score,
                match_tier,
                reasoning_summary,
                inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def write_candidate_skills(self, candidate: Candidate) -> int:
        rows = [
            (skill, group, True)
            for group, skills in candidate.skills.items()
            for skill in skills
        ]
        if not rows:
            return 0

        with self.service.connect() as conn:
            conn.executemany(
                """
                insert or replace into staging.python_candidate_skills (
                    skill,
                    skill_group,
                    in_candidate_profile
                )
                values (?, ?, ?)
                """,
                rows,
            )
        return len(rows)
