"""PostgreSQL-backed user pipeline queue and run history."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.repositories.errors import (
    InvalidStateTransitionError,
    NotFoundError,
    PipelineAlreadyActiveError,
    PipelineDailyLimitError,
)
from packages.careersignal_core.storage.postgres import PostgresStore


PUBLIC_RUN_COLUMNS = """
run_uuid, user_uuid, status::text as status, config_hash, config_revision_map,
submitted_at, started_at, completed_at, published_at, jobs_considered, jobs_matched,
error_code, public_error_message, is_current_result, source_connector_run_uuid,
is_bootstrap_run, trigger_type, bootstrap_uuid, config_bundle_revision_uuid
"""

QUOTA_WINDOW_START_SQL = "date_trunc('day', now() at time zone 'UTC') at time zone 'UTC'"


class PipelineRunRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def create(
        self,
        *,
        user_uuid: UUID | str,
        snapshot: dict[str, Any],
        daily_limit: int | None,
        status: str = "queued",
        source_connector_run_uuid: UUID | str | None = None,
        is_bootstrap_run: bool = False,
        trigger_type: str = "user_manual",
        bootstrap_uuid: UUID | str | None = None,
        connection: Any | None = None,
    ) -> dict[str, Any]:
        def _create(active_connection: Any) -> dict[str, Any]:
            if daily_limit is not None:
                recent = active_connection.execute(
                    f"""
                    select count(*) as count
                    from public.user_pipeline_runs
                    where user_uuid = %s
                      and submitted_at >= {QUOTA_WINDOW_START_SQL}
                      and submitted_at < {QUOTA_WINDOW_START_SQL} + interval '1 day'
                      and status = 'completed'
                    """,
                    [str(user_uuid)],
                ).fetchone()
                if int(recent["count"]) >= daily_limit:
                    raise PipelineDailyLimitError("Daily pipeline limit reached")
            try:
                row = active_connection.execute(
                    f"""
                    insert into public.user_pipeline_runs (
                        user_uuid, status, config_snapshot, config_hash, config_revision_map,
                        source_connector_run_uuid, is_bootstrap_run, trigger_type, bootstrap_uuid,
                        config_bundle_revision_uuid
                    ) values (%s, %s::public.pipeline_status, %s, %s, %s, %s, %s, %s, %s, %s)
                    returning {PUBLIC_RUN_COLUMNS}
                    """,
                    [
                        str(user_uuid),
                        status,
                        Jsonb(snapshot),
                        snapshot["config_hash"],
                        Jsonb(snapshot.get("config_revision_map", {})),
                        str(source_connector_run_uuid) if source_connector_run_uuid else None,
                        is_bootstrap_run,
                        trigger_type,
                        str(bootstrap_uuid) if bootstrap_uuid else None,
                        snapshot.get("config_bundle_revision_uuid"),
                    ],
                ).fetchone()
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise PipelineAlreadyActiveError("A pipeline run is already queued or running") from exc
                raise
            active_connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', %s, %s)
                """,
                [
                    row["run_uuid"],
                    str(user_uuid),
                    "waiting_for_global" if status == "waiting_for_global" else "queued",
                    (
                        "First refresh is waiting for the shared job dataset to refresh"
                        if status == "waiting_for_global"
                        else "Pipeline run queued"
                    ),
                ],
            )
            return dict(row)

        if connection is not None:
            return _create(connection)
        with self.store.transaction() as transaction:
            return _create(transaction)

    def quota_for_user(
        self,
        user_uuid: UUID | str,
        *,
        daily_limit: int | None,
    ) -> dict[str, Any]:
        row = self.store.fetch_one(
            f"""
            select
                count(*) filter (where status = 'completed')::integer as used,
                {QUOTA_WINDOW_START_SQL} as window_start,
                {QUOTA_WINDOW_START_SQL} + interval '1 day' as window_end
            from public.user_pipeline_runs
            where user_uuid = %s
              and submitted_at >= {QUOTA_WINDOW_START_SQL}
              and submitted_at < {QUOTA_WINDOW_START_SQL} + interval '1 day'
            """,
            [str(user_uuid)],
        ) or {}
        used = int(row.get("used") or 0)
        return {
            "limit": daily_limit,
            "used": used,
            "remaining": None if daily_limit is None else max(0, daily_limit - used),
            "window_start": row.get("window_start"),
            "window_end": row.get("window_end"),
            "resets_at": row.get("window_end"),
        }

    def list_for_user(self, user_uuid: UUID | str, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return self.store.fetch_all(
            f"""
            select {PUBLIC_RUN_COLUMNS}
            from public.user_pipeline_runs
            where user_uuid = %s
            order by submitted_at desc
            limit %s offset %s
            """,
            [str(user_uuid), limit, offset],
        )

    def get_for_user(self, user_uuid: UUID | str, run_uuid: UUID | str) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            f"""
            select {PUBLIC_RUN_COLUMNS}
            from public.user_pipeline_runs
            where user_uuid = %s and run_uuid = %s
            """,
            [str(user_uuid), str(run_uuid)],
        )
        if row is not None:
            row["events"] = self.store.fetch_all(
                """
                select event_uuid, event_level, event_type, message, created_at
                from public.user_pipeline_run_events
                where user_uuid = %s and run_uuid = %s
                order by created_at
                """,
                [str(user_uuid), str(run_uuid)],
            )
        return row

    def cancel_queued(self, user_uuid: UUID | str, run_uuid: UUID | str) -> dict[str, Any]:
        row = self.store.fetch_one(
            f"""
            update public.user_pipeline_runs
            set status = 'cancelled', completed_at = now()
            where user_uuid = %s and run_uuid = %s and status = 'queued'
            returning {PUBLIC_RUN_COLUMNS}
            """,
            [str(user_uuid), str(run_uuid)],
        )
        if row is None:
            existing = self.get_for_user(user_uuid, run_uuid)
            if existing is None:
                raise NotFoundError("Pipeline run was not found")
            raise InvalidStateTransitionError("Only queued pipeline runs may be cancelled")
        return row

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        with self.store.transaction() as connection:
            row = connection.execute(
                """
                select run_uuid
                from public.user_pipeline_runs
                where status = 'queued'
                order by submitted_at
                for update skip locked
                limit 1
                """
            ).fetchone()
            if row is None:
                return None
            claimed = connection.execute(
                """
                update public.user_pipeline_runs
                set status = 'running', started_at = now(), worker_id = %s
                where run_uuid = %s and status = 'queued'
                returning run_uuid, user_uuid, config_snapshot, config_hash, config_revision_map,
                          submitted_at, started_at, worker_id, source_connector_run_uuid,
                          is_bootstrap_run, trigger_type, bootstrap_uuid,
                          config_bundle_revision_uuid
                """,
                [worker_id, row["run_uuid"]],
            ).fetchone()
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'started', 'Worker started user dbt refresh')
                """,
                [claimed["run_uuid"], claimed["user_uuid"]],
            )
            return dict(claimed)

    def queue_after_global(
        self,
        *,
        run_uuid: UUID | str,
        source_connector_run_uuid: UUID | str,
    ) -> dict[str, Any]:
        with self.store.transaction() as connection:
            row = connection.execute(
                f"""
                update public.user_pipeline_runs
                set status = 'queued',
                    source_connector_run_uuid = %s
                where run_uuid = %s and status = 'waiting_for_global'
                returning {PUBLIC_RUN_COLUMNS}
                """,
                [str(source_connector_run_uuid), str(run_uuid)],
            ).fetchone()
            if row is None:
                raise InvalidStateTransitionError("Only waiting bootstrap runs may be queued")
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'global_refresh_completed',
                          'Shared job dataset refreshed; personal dbt run queued')
                """,
                [str(run_uuid), row["user_uuid"]],
            )
            return dict(row)

    def add_event(
        self,
        *,
        run_uuid: UUID | str,
        user_uuid: UUID | str,
        event_type: str,
        message: str,
        level: str = "info",
    ) -> None:
        self.store.execute(
            """
            insert into public.user_pipeline_run_events (
                run_uuid, user_uuid, event_level, event_type, message
            ) values (%s, %s, %s, %s, %s)
            """,
            [str(run_uuid), str(user_uuid), level, event_type, message[:2000]],
        )

    def requeue(self, *, run_uuid: UUID | str, reason: str) -> None:
        """Return a claimed run to the queue when shared writer capacity is busy."""

        with self.store.transaction() as connection:
            row = connection.execute(
                """
                update public.user_pipeline_runs
                set status = 'queued', started_at = null, worker_id = null
                where run_uuid = %s and status = 'running'
                returning user_uuid
                """,
                [str(run_uuid)],
            ).fetchone()
            if row is None:
                raise InvalidStateTransitionError("Only a running pipeline may be requeued")
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'requeued', %s)
                """,
                [str(run_uuid), row["user_uuid"], reason[:2000]],
            )

    def fail(
        self,
        *,
        run_uuid: UUID | str,
        error_code: str,
        public_message: str,
        internal_message: str,
    ) -> None:
        with self.store.transaction() as connection:
            row = connection.execute(
                """
                update public.user_pipeline_runs
                set status = 'failed', completed_at = now(), error_code = %s,
                    public_error_message = %s, internal_error_message = %s
                where run_uuid = %s and status = 'running'
                returning user_uuid
                """,
                [error_code, public_message, internal_message[:8000], str(run_uuid)],
            ).fetchone()
            if row is not None:
                connection.execute(
                    """
                    insert into public.user_pipeline_run_events (
                        run_uuid, user_uuid, event_level, event_type, message
                    ) values (%s, %s, 'error', 'failed', %s)
                    """,
                    [str(run_uuid), row["user_uuid"], public_message[:2000]],
                )
