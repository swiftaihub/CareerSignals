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
error_code, public_error_message, is_current_result
"""


class PipelineRunRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def create(
        self,
        *,
        user_uuid: UUID | str,
        snapshot: dict[str, Any],
        daily_limit: int | None,
    ) -> dict[str, Any]:
        with self.store.transaction() as connection:
            if daily_limit is not None:
                recent = connection.execute(
                    """
                    select count(*) as count
                    from public.user_pipeline_runs
                    where user_uuid = %s and submitted_at >= date_trunc('day', now() at time zone 'UTC')
                      and status <> 'cancelled'
                    """,
                    [str(user_uuid)],
                ).fetchone()
                if int(recent["count"]) >= daily_limit:
                    raise PipelineDailyLimitError("Daily pipeline limit reached")
            try:
                row = connection.execute(
                    f"""
                    insert into public.user_pipeline_runs (
                        user_uuid, config_snapshot, config_hash, config_revision_map
                    ) values (%s, %s, %s, %s)
                    returning {PUBLIC_RUN_COLUMNS}
                    """,
                    [
                        str(user_uuid),
                        Jsonb(snapshot),
                        snapshot["config_hash"],
                        Jsonb(snapshot.get("config_revision_map", {})),
                    ],
                ).fetchone()
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise PipelineAlreadyActiveError("A pipeline run is already queued or running") from exc
                raise
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'queued', 'Pipeline run queued')
                """,
                [row["run_uuid"], str(user_uuid)],
            )
        return dict(row)

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
                          submitted_at, started_at, worker_id
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
