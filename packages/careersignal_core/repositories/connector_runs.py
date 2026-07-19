"""Metadata repository for system-owned connector refreshes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.repositories.errors import ConflictError
from packages.careersignal_core.storage.postgres import PostgresStore


PUBLIC_CONNECTOR_RUN_COLUMNS = """
connector_run_uuid, status::text as status, trigger_type, scheduled_for,
started_at, completed_at, next_scheduled_at, shared_dbt_run_completed,
jobs_fetched, jobs_retained, jobs_published, public_status_message,
error_code, created_at, initiating_user_uuid, bootstrap_uuid,
initiating_user_included, initiating_config_revision_map, initiating_config_hash,
initiating_acquisition_hash, resulting_personal_run_uuid, included_user_count,
acquisition_query_count
"""

CONNECTOR_TRIGGER_TYPES = frozenset(
    {"scheduled", "manual_admin", "manual_cli", "first_user_bootstrap", "internal", "admin"}
)


def _validated_trigger_type(trigger_type: str) -> str:
    if trigger_type not in CONNECTOR_TRIGGER_TYPES:
        allowed = ", ".join(sorted(CONNECTOR_TRIGGER_TYPES))
        raise ValueError(f"Unsupported connector refresh trigger_type {trigger_type!r}; expected {allowed}")
    return trigger_type


def _utc_timestamp(value: datetime | None, *, field: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


class ConnectorRunRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def create(
        self,
        *,
        trigger_type: str,
        scheduled_for: datetime | None = None,
        next_scheduled_at: datetime | None = None,
        initiating_user_uuid: UUID | str | None = None,
        bootstrap_uuid: UUID | str | None = None,
        initiating_config_revision_map: dict[str, Any] | None = None,
        initiating_config_hash: str | None = None,
        initiating_acquisition_hash: str | None = None,
        resulting_personal_run_uuid: UUID | str | None = None,
        connection: Any | None = None,
    ) -> dict[str, Any]:
        statement = f"""
            insert into public.connector_refresh_runs (
                status, trigger_type, scheduled_for, next_scheduled_at,
                initiating_user_uuid, bootstrap_uuid, initiating_config_revision_map,
                initiating_config_hash, initiating_acquisition_hash,
                resulting_personal_run_uuid
            ) values ('queued', %s, %s, %s, %s, %s, %s, %s, %s, %s)
            returning {PUBLIC_CONNECTOR_RUN_COLUMNS}
            """
        params = [
            _validated_trigger_type(trigger_type),
            _utc_timestamp(scheduled_for, field="scheduled_for"),
            _utc_timestamp(next_scheduled_at, field="next_scheduled_at"),
            str(initiating_user_uuid) if initiating_user_uuid else None,
            str(bootstrap_uuid) if bootstrap_uuid else None,
            Jsonb(initiating_config_revision_map) if initiating_config_revision_map is not None else None,
            initiating_config_hash,
            initiating_acquisition_hash,
            str(resulting_personal_run_uuid) if resulting_personal_run_uuid else None,
        ]
        row = (
            connection.execute(statement, params).fetchone()
            if connection is not None
            else self.store.fetch_one(statement, params)
        )
        assert row is not None
        return dict(row)

    def create_if_no_active(
        self,
        *,
        trigger_type: str,
        scheduled_for: datetime | None = None,
        next_scheduled_at: datetime | None = None,
    ) -> dict[str, Any]:
        _validated_trigger_type(trigger_type)
        with self.store.transaction() as connection:
            # A row lock cannot serialize the empty-table case. This transaction
            # lock makes the active check and insert atomic across all enqueuers.
            connection.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ["careersignals:global-connector-refresh-enqueue"],
            )
            active = connection.execute(
                f"""
                select {PUBLIC_CONNECTOR_RUN_COLUMNS}
                from public.connector_refresh_runs
                where status in ('queued', 'running')
                order by created_at
                for update
                limit 1
                """
            ).fetchone()
            if active is not None:
                raise ConflictError("A global connector refresh is already queued or running")
            return self.create(
                trigger_type=trigger_type,
                scheduled_for=scheduled_for,
                next_scheduled_at=next_scheduled_at,
                connection=connection,
            )

    def get(self, connector_run_uuid: UUID | str) -> dict[str, Any] | None:
        return self.store.fetch_one(
            f"""
            select {PUBLIC_CONNECTOR_RUN_COLUMNS}
            from public.connector_refresh_runs
            where connector_run_uuid = %s
            """,
            [str(connector_run_uuid)],
        )

    def claim_next(self) -> dict[str, Any] | None:
        with self.store.transaction() as connection:
            row = connection.execute(
                """
                select connector_run_uuid
                from public.connector_refresh_runs
                where status = 'queued'
                order by created_at
                for update skip locked
                limit 1
                """
            ).fetchone()
            if row is None:
                return None
            claimed = connection.execute(
                f"""
                update public.connector_refresh_runs
                set status = 'running', started_at = now()
                where connector_run_uuid = %s and status = 'queued'
                returning {PUBLIC_CONNECTOR_RUN_COLUMNS}
                """,
                [row["connector_run_uuid"]],
            ).fetchone()
            return dict(claimed) if claimed is not None else None

    def start(self, connector_run_uuid: UUID | str) -> None:
        self.store.execute(
            """
            update public.connector_refresh_runs
            set status = 'running', started_at = now()
            where connector_run_uuid = %s and status = 'queued'
            """,
            [str(connector_run_uuid)],
        )

    def requeue(self, connector_run_uuid: UUID | str, *, public_status_message: str) -> None:
        self.store.execute(
            """
            update public.connector_refresh_runs
            set status = 'queued',
                started_at = null,
                public_status_message = %s
            where connector_run_uuid = %s and status = 'running'
            """,
            [public_status_message, str(connector_run_uuid)],
        )

    def fail_stale_running(self, *, max_age_seconds: int) -> int:
        """Close orphaned runs after a worker restart releases their session locks."""

        return self.store.execute(
            """
            update public.connector_refresh_runs
            set status = 'failed',
                completed_at = now(),
                shared_dbt_run_completed = false,
                public_status_message = 'The shared-data refresh exceeded its execution window and was stopped.',
                error_code = 'CONNECTOR_REFRESH_STALE',
                internal_error_message = 'Connector refresh exceeded the configured execution window.'
            where status = 'running'
              and started_at < now() - (%s * interval '1 second')
            """,
            [max_age_seconds],
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

    def latest_successful(self) -> dict[str, Any] | None:
        return self.store.fetch_one(
            f"""
            select {PUBLIC_CONNECTOR_RUN_COLUMNS}
            from public.connector_refresh_runs
            where status in ('completed', 'partial')
              and completed_at is not null
              and shared_dbt_run_completed
            order by completed_at desc
            limit 1
            """
        )

    def record_acquisition_audit(
        self,
        *,
        connector_run_uuid: UUID | str,
        user_snapshots: list[dict[str, Any]],
        acquisition_queries: list[dict[str, Any]],
    ) -> None:
        with self.store.transaction() as connection:
            for snapshot in user_snapshots:
                connection.execute(
                    """
                    insert into public.connector_run_user_config_snapshots (
                        connector_run_uuid, user_uuid, config_revisions,
                        effective_config_hashes, acquisition_config, acquisition_hash
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict (connector_run_uuid, user_uuid) do update set
                        config_revisions = excluded.config_revisions,
                        effective_config_hashes = excluded.effective_config_hashes,
                        acquisition_config = excluded.acquisition_config,
                        acquisition_hash = excluded.acquisition_hash
                    """,
                    [
                        str(connector_run_uuid),
                        str(snapshot["user_uuid"]),
                        Jsonb(snapshot.get("config_revisions") or {}),
                        Jsonb(snapshot.get("effective_config_hashes") or {}),
                        Jsonb(snapshot.get("acquisition_config") or {}),
                        str(snapshot.get("acquisition_hash") or ""),
                    ],
                )
            for query in acquisition_queries:
                connection.execute(
                    """
                    insert into public.connector_acquisition_queries (
                        connector_run_uuid, query_key, source_name, request_json,
                        interested_user_count, status, records_fetched,
                        internal_error_message
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (connector_run_uuid, query_key) do update set
                        request_json = excluded.request_json,
                        interested_user_count = excluded.interested_user_count,
                        status = excluded.status,
                        records_fetched = excluded.records_fetched,
                        internal_error_message = excluded.internal_error_message,
                        updated_at = now()
                    """,
                    [
                        str(connector_run_uuid),
                        str(query["query_key"]),
                        str(query["source_name"]),
                        Jsonb(query.get("request_json") or {}),
                        int(query.get("interested_user_count") or 0),
                        str(query.get("status") or "planned"),
                        int(query.get("records_fetched") or 0),
                        query.get("internal_error_message"),
                    ],
                )
            connection.execute(
                """
                update public.connector_refresh_runs
                set included_user_count = %s,
                    acquisition_query_count = %s,
                    initiating_user_included = case
                        when initiating_user_uuid is null then false
                        else exists (
                            select 1
                            from public.connector_run_user_config_snapshots s
                            where s.connector_run_uuid = connector_refresh_runs.connector_run_uuid
                              and s.user_uuid = connector_refresh_runs.initiating_user_uuid
                        )
                    end
                where connector_run_uuid = %s
                """,
                [len(user_snapshots), len(acquisition_queries), str(connector_run_uuid)],
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

    def admin_list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            f"""
            select {PUBLIC_CONNECTOR_RUN_COLUMNS}
            from public.connector_refresh_runs
            order by created_at desc
            limit %s
            """,
            [limit],
        )
