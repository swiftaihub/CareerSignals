"""Metadata repository for system-owned connector refreshes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from packages.careersignal_core.storage.postgres import PostgresStore


class ConnectorRunRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def create(
        self,
        *,
        trigger_type: str,
        scheduled_for: datetime | None = None,
        next_scheduled_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = self.store.fetch_one(
            """
            insert into public.connector_refresh_runs (
                status, trigger_type, scheduled_for, next_scheduled_at
            ) values ('queued', %s, %s, %s)
            returning connector_run_uuid, status::text as status, trigger_type, created_at
            """,
            [trigger_type, scheduled_for, next_scheduled_at],
        )
        assert row is not None
        return row

    def start(self, connector_run_uuid: UUID | str) -> None:
        self.store.execute(
            """
            update public.connector_refresh_runs
            set status = 'running', started_at = now()
            where connector_run_uuid = %s and status = 'queued'
            """,
            [str(connector_run_uuid)],
        )

    def finish(
        self,
        *,
        connector_run_uuid: UUID | str,
        status: str,
        jobs_fetched: int,
        jobs_retained: int,
        jobs_published: int,
        shared_dbt_run_completed: bool,
        public_status_message: str,
        error_code: str | None = None,
        internal_error_message: str | None = None,
    ) -> None:
        self.store.execute(
            """
            update public.connector_refresh_runs
            set status = %s::public.connector_run_status, completed_at = now(),
                jobs_fetched = %s, jobs_retained = %s, jobs_published = %s,
                shared_dbt_run_completed = %s, public_status_message = %s,
                error_code = %s, internal_error_message = %s
            where connector_run_uuid = %s
            """,
            [
                status,
                jobs_fetched,
                jobs_retained,
                jobs_published,
                shared_dbt_run_completed,
                public_status_message,
                error_code,
                internal_error_message[:8000] if internal_error_message else None,
                str(connector_run_uuid),
            ],
        )

    def upsert_source_result(
        self,
        *,
        connector_run_uuid: UUID | str,
        source_name: str,
        status: str,
        records_fetched: int,
        records_retained: int,
        public_status_message: str,
        internal_error_message: str | None = None,
    ) -> None:
        self.store.execute(
            """
            insert into public.connector_source_runs (
                connector_run_uuid, source_name, status, started_at, completed_at,
                records_fetched, records_retained, public_status_message, internal_error_message
            ) values (%s, %s, %s::public.connector_run_status, now(), now(), %s, %s, %s, %s)
            on conflict (connector_run_uuid, source_name) do update set
                status = excluded.status,
                completed_at = excluded.completed_at,
                records_fetched = excluded.records_fetched,
                records_retained = excluded.records_retained,
                public_status_message = excluded.public_status_message,
                internal_error_message = excluded.internal_error_message
            """,
            [
                str(connector_run_uuid), source_name, status, records_fetched, records_retained,
                public_status_message, internal_error_message[:8000] if internal_error_message else None,
            ],
        )

    def freshness(self, *, stale_after_hours: int) -> dict[str, Any]:
        overall = self.store.fetch_one(
            """
            select
              completed_at as last_successful_refresh_at,
              next_scheduled_at,
              completed_at as data_as_of,
              completed_at is null or completed_at < now() - (%s * interval '1 hour') as is_stale,
              case
                when completed_at is null then 'unavailable'
                when completed_at < now() - (%s * interval '1 hour') then 'stale'
                else 'healthy'
              end as status,
              connector_run_uuid
            from public.connector_refresh_runs
            where status in ('completed', 'partial')
            order by completed_at desc nulls last
            limit 1
            """,
            [stale_after_hours, stale_after_hours],
        )
        if overall is None:
            return {
                "overall": {
                    "last_successful_refresh_at": None,
                    "next_scheduled_refresh_at": None,
                    "data_as_of": None,
                    "is_stale": True,
                    "status": "unavailable",
                },
                "sources": [],
            }
        sources = self.store.fetch_all(
            """
            select source_name, completed_at as last_successful_refresh_at,
                   records_retained, status::text as status, public_status_message
            from public.connector_source_runs
            where connector_run_uuid = %s
            order by source_name
            """,
            [overall.pop("connector_run_uuid")],
        )
        overall["next_scheduled_refresh_at"] = overall.pop("next_scheduled_at")
        return {"overall": overall, "sources": sources}
