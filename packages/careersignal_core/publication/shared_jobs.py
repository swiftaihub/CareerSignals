"""Idempotent publisher for the shared canonical job universe."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping
from uuid import UUID

from packages.careersignal_core.storage.postgres import PostgresStore


SHARED_JOB_COLUMNS = (
    "job_id",
    "source_name",
    "source_job_id",
    "title",
    "company_name",
    "location",
    "location_group",
    "industry",
    "seniority",
    "work_arrangement",
    "visa_signal",
    "salary_min",
    "salary_max",
    "salary_currency",
    "posted_at",
    "apply_url",
    "job_description",
    "job_description_hash",
    "first_seen_at",
    "last_seen_at",
)


class SharedJobPublicationError(RuntimeError):
    pass


class SharedJobsPublisher:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def publish_shared_jobs(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        connector_run_uuid: UUID | str,
    ) -> int:
        return self.publish(records, connector_run_uuid=connector_run_uuid)

    def publish(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        connector_run_uuid: UUID | str,
        inactive_after_days: int = 30,
    ) -> int:
        try:
            run_uuid = str(UUID(str(connector_run_uuid)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise SharedJobPublicationError("connector_run_uuid must be a valid UUID") from exc
        jobs: list[dict[str, Any]] = []
        for original in rows:
            row = dict(original)
            if "user_uuid" in row:
                raise SharedJobPublicationError("Shared job output must not contain user ownership")
            description = str(row.get("job_description") or "")
            normalized = {
                **row,
                "source_name": row.get("source_name", row.get("source")),
                "title": row.get("title", row.get("job_title")),
                "company_name": row.get("company_name", row.get("company")),
                "apply_url": row.get("apply_url", row.get("jd_post_link")),
                "salary_currency": row.get("salary_currency") or "USD",
                "job_description_hash": row.get("job_description_hash")
                or hashlib.sha256(description.encode("utf-8")).hexdigest(),
            }
            jobs.append(normalized)
        if len({str(row.get("job_id")) for row in jobs}) != len(jobs):
            raise SharedJobPublicationError("Shared job output contains duplicate job IDs")
        if any(not row.get("job_id") or not row.get("title") or not row.get("source_name") for row in jobs):
            raise SharedJobPublicationError("Shared job output is missing a required field")
        if any(not row.get("first_seen_at") or not row.get("last_seen_at") for row in jobs):
            raise SharedJobPublicationError("Shared job output is missing freshness timestamps")

        with self.store.transaction() as connection:
            for row in jobs:
                values = [row.get(column) for column in SHARED_JOB_COLUMNS]
                connection.execute(
                    """
                    insert into public.job_postings (
                        job_id, source_name, source_job_id, title, company_name, location,
                        location_group, industry, seniority, work_arrangement, visa_signal,
                        salary_min, salary_max, salary_currency, posted_at, apply_url,
                        job_description, job_description_hash, first_seen_at, last_seen_at,
                        shared_connector_run_uuid, updated_at, is_active
                    ) values (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), true
                    )
                    on conflict (job_id) do update set
                        source_name = excluded.source_name,
                        source_job_id = excluded.source_job_id,
                        title = excluded.title,
                        company_name = excluded.company_name,
                        location = excluded.location,
                        location_group = excluded.location_group,
                        industry = excluded.industry,
                        seniority = excluded.seniority,
                        work_arrangement = excluded.work_arrangement,
                        visa_signal = excluded.visa_signal,
                        salary_min = excluded.salary_min,
                        salary_max = excluded.salary_max,
                        salary_currency = excluded.salary_currency,
                        posted_at = excluded.posted_at,
                        apply_url = excluded.apply_url,
                        job_description = excluded.job_description,
                        job_description_hash = excluded.job_description_hash,
                        first_seen_at = least(job_postings.first_seen_at, excluded.first_seen_at),
                        last_seen_at = greatest(job_postings.last_seen_at, excluded.last_seen_at),
                        shared_connector_run_uuid = excluded.shared_connector_run_uuid,
                        updated_at = now(),
                        is_active = true
                    """,
                    [*values, run_uuid],
                )
            connection.execute(
                """
                update public.job_postings
                set is_active = false, updated_at = now()
                where is_active = true
                  and last_seen_at < now() - (%s * interval '1 day')
                  and shared_connector_run_uuid is distinct from %s
                """,
                [inactive_after_days, run_uuid],
            )
        return len(jobs)
