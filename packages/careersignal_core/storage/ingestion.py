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


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    text = clean_text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


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
                    job.get("location_normalized"),
                    job.get("location_group"),
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
                    job.get("visa_status"),
                    job.get("visa_evidence"),
                    job.get("visa_confidence"),
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

    def write_shared_jobs(
        self,
        connector_run_uuid: str,
        jobs: list[dict[str, Any]],
        progress: ProgressReporter | None = None,
    ) -> int:
        """Write candidate-independent shared job observations for one Connector run."""

        observed_at = _now()
        rows: list[tuple[Any, ...]] = []
        observations: list[tuple[Any, ...]] = []
        jobs_iterable = (
            progress.iter(jobs, "Writing shared MotherDuck bridge rows", total=len(jobs))
            if progress
            else jobs
        )
        for job in jobs_iterable:
            job_id = clean_text(job.get("job_id"))
            if not job_id:
                continue
            posted_at = _timestamp(job.get("posted_at") or job.get("date_posted"))
            first_seen_at = _timestamp(job.get("first_seen_at")) or observed_at
            last_seen_at = _timestamp(job.get("last_seen_at")) or observed_at
            source = clean_text(job.get("source"))
            source_job_id = clean_text(job.get("source_job_id")) or None
            source_url = clean_text(job.get("jd_post_link") or job.get("apply_link"))
            rows.append(
                (
                    job_id,
                    connector_run_uuid,
                    source,
                    source_job_id,
                    clean_text(job.get("category_name")),
                    clean_text(job.get("job_title")),
                    clean_text(job.get("normalized_title")),
                    clean_text(job.get("company")),
                    clean_text(job.get("normalized_company") or job.get("company")).casefold(),
                    clean_text(job.get("industry") or "Unknown"),
                    clean_text(job.get("location") or "Unknown"),
                    clean_text(job.get("location_normalized") or "Unknown"),
                    clean_text(job.get("location_group") or "Other or Unclassified"),
                    clean_text(job.get("work_arrangement") or "Unknown"),
                    clean_text(job.get("employment_type") or "full-time"),
                    clean_text(job.get("seniority") or "Unknown"),
                    job.get("salary_min"),
                    job.get("salary_max"),
                    job.get("salary_midpoint"),
                    clean_text(job.get("salary_range_text")) or None,
                    clean_text(job.get("date_posted")) or None,
                    posted_at,
                    clean_text(job.get("date_collected")),
                    source_url,
                    clean_text(job.get("apply_link")) or None,
                    clean_text(job.get("job_description")),
                    clean_text(job.get("normalized_description") or job.get("job_description")).casefold(),
                    clean_text(job.get("visa_signal") or "Unknown"),
                    clean_text(job.get("visa_status") or "Unknown"),
                    clean_text(job.get("visa_evidence")) or None,
                    clean_text(job.get("visa_confidence") or "Low"),
                    first_seen_at,
                    last_seen_at,
                    observed_at,
                )
            )
            observations.append(
                (
                    stable_hash(connector_run_uuid, job_id, source, length=32),
                    connector_run_uuid,
                    job_id,
                    source,
                    source_job_id,
                    observed_at,
                    source_url,
                )
            )

        if not rows:
            return 0
        columns = """
            job_id, connector_run_uuid, source, source_job_id, category_name,
            job_title, normalized_title, company, normalized_company, industry,
            location, location_normalized, location_group, work_arrangement,
            employment_type, seniority, salary_min, salary_max, salary_midpoint,
            salary_range_text, date_posted, posted_at, date_collected,
            jd_post_link, apply_link, job_description, normalized_description,
            visa_signal, visa_status, visa_evidence, visa_confidence,
            first_seen_at, last_seen_at, inserted_at
        """
        placeholders = ", ".join("?" for _ in rows[0])
        with self.service.connect() as conn:
            conn.executemany(
                f"insert or replace into staging.shared_jobs_processed ({columns}) values ({placeholders})",
                rows,
            )
            conn.executemany(
                """
                insert or replace into staging.shared_job_observations (
                    observation_id, connector_run_uuid, job_id, source,
                    source_job_id, observed_at, source_url
                ) values (?, ?, ?, ?, ?, ?, ?)
                """,
                observations,
            )
        return len(rows)

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
                location_normalized,
                location_group,
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
                visa_status,
                visa_evidence,
                visa_confidence,
                match_score,
                match_tier,
                reasoning_summary,
                inserted_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def write_user_config_snapshot(
        self,
        user_uuid: str,
        run_uuid: str,
        snapshot: dict[str, Any],
    ) -> dict[str, int]:
        """Replace exactly one staged user/run config partition transactionally."""

        configs = snapshot.get("configs")
        if not isinstance(configs, dict):
            raise ValueError("config snapshot must contain a configs mapping")
        candidate_document = configs.get("candidate_profile") or {}
        jobs_document = configs.get("jobs_config") or {}
        taxonomy_document = configs.get("skill_taxonomy") or {}
        candidate = candidate_document.get("candidate") or {}
        weights = jobs_document.get("ranking_weights") or {}
        filters = jobs_document.get("global_filters") or {}
        output = jobs_document.get("output") or {}
        config_hash = clean_text(snapshot.get("config_hash"))
        if not config_hash:
            raise ValueError("config snapshot must contain config_hash")
        staged_at = _now()

        candidate_rows = [
            (user_uuid, run_uuid, config_hash, skill, group, True, staged_at)
            for group, skills in (candidate.get("skills") or {}).items()
            for skill in skills
            if clean_text(skill)
        ]
        preference_rows = [
            (
                user_uuid,
                run_uuid,
                config_hash,
                category.get("category_name"),
                canonical_json(category.get("search_titles") or []),
                canonical_json(category.get("industries") or []),
                canonical_json(category.get("seniority") or []),
                canonical_json(candidate.get("target_titles") or []),
                canonical_json(candidate.get("target_industries") or []),
                canonical_json(filters.get("locations") or []),
                canonical_json(
                    (candidate.get("required_preferences") or {}).get("work_arrangement")
                    or filters.get("work_type")
                    or []
                ),
                canonical_json(filters.get("employment_type") or []),
                canonical_json(filters.get("visa_preferences") or []),
                canonical_json(filters.get("excluded_companies") or []),
                canonical_json(filters.get("excluded_titles") or []),
                (candidate.get("salary_expectation") or {}).get("min_base_salary", 0),
                (candidate.get("salary_expectation") or {}).get("preferred_base_salary", 0),
                weights.get("title_match", 0.25),
                weights.get("required_skill_match", 0.25),
                weights.get("industry_match", 0.20),
                weights.get("salary_match", 0.10),
                weights.get("work_arrangement_match", 0.10),
                weights.get("visa_signal_match", 0.10),
                output.get("top_match_threshold", 80),
                staged_at,
            )
            for category in jobs_document.get("job_categories") or []
        ]
        alias_rows_set: set[tuple[str, str]] = set()
        for alias_config in (taxonomy_document.get("skill_aliases") or {}).values():
            canonical = clean_text(alias_config.get("canonical"))
            for alias in [canonical, *(alias_config.get("aliases") or [])]:
                normalized_alias = clean_text(alias)
                if canonical and normalized_alias:
                    alias_rows_set.add((canonical, normalized_alias))
        for _, _, _, skill, _, _, _ in candidate_rows:
            alias_rows_set.add((skill, skill))
        alias_rows = [
            (user_uuid, run_uuid, config_hash, canonical, alias, staged_at)
            for canonical, alias in sorted(alias_rows_set, key=lambda pair: (pair[0].casefold(), pair[1].casefold()))
        ]

        with self.service.connect() as conn:
            conn.execute("begin transaction")
            try:
                for table in (
                    "app.user_config_snapshots",
                    "app.user_candidate_skills",
                    "app.user_job_preferences",
                    "app.user_skill_aliases",
                ):
                    conn.execute(
                        f"delete from {table} where user_uuid = ? and run_uuid = ?",
                        [user_uuid, run_uuid],
                    )
                conn.execute(
                    """
                    insert into app.user_config_snapshots (
                        user_uuid, run_uuid, config_hash, snapshot_version,
                        config_revision_map, config_snapshot, staged_at
                    ) values (?, ?, ?, ?, cast(? as json), cast(? as json), ?)
                    """,
                    [
                        user_uuid,
                        run_uuid,
                        config_hash,
                        int(snapshot.get("schema_version") or 1),
                        canonical_json(snapshot.get("config_revision_map") or {}),
                        canonical_json(snapshot),
                        staged_at,
                    ],
                )
                if candidate_rows:
                    conn.executemany(
                        """
                        insert into app.user_candidate_skills (
                            user_uuid, run_uuid, config_hash, skill, skill_group,
                            in_candidate_profile, staged_at
                        ) values (?, ?, ?, ?, ?, ?, ?)
                        """,
                        candidate_rows,
                    )
                if preference_rows:
                    placeholders = ", ".join("?" for _ in preference_rows[0])
                    conn.executemany(
                        f"""
                        insert into app.user_job_preferences (
                            user_uuid, run_uuid, config_hash, category_name,
                            search_titles, industries, seniority, target_titles,
                            target_industries, locations, work_arrangements,
                            employment_types, visa_preferences, excluded_companies,
                            excluded_titles, min_base_salary, preferred_base_salary,
                            title_match_weight, required_skill_match_weight,
                            industry_match_weight, salary_match_weight,
                            work_arrangement_match_weight, visa_signal_match_weight,
                            top_match_threshold, staged_at
                        ) values ({placeholders})
                        """,
                        preference_rows,
                    )
                if alias_rows:
                    conn.executemany(
                        """
                        insert into app.user_skill_aliases (
                            user_uuid, run_uuid, config_hash, canonical_skill,
                            alias, staged_at
                        ) values (?, ?, ?, ?, ?, ?)
                        """,
                        alias_rows,
                    )
                conn.execute("commit")
            except Exception:
                conn.execute("rollback")
                raise

        return {
            "candidate_skills": len(candidate_rows),
            "job_preferences": len(preference_rows),
            "skill_aliases": len(alias_rows),
        }
