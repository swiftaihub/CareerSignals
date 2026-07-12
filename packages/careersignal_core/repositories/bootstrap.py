"""Durable first-user bootstrap orchestration state."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.errors import (
    InvalidStateTransitionError,
    NotFoundError,
    PipelineAlreadyActiveError,
    PipelineDailyLimitError,
)
from packages.careersignal_core.repositories.pipeline_runs import (
    PUBLIC_RUN_COLUMNS,
    QUOTA_WINDOW_START_SQL,
    PipelineRunRepository,
)
from packages.careersignal_core.storage.postgres import PostgresStore


BOOTSTRAP_COLUMNS = """
bootstrap_uuid, user_uuid, status, personal_run_uuid, connector_run_uuid,
config_snapshot, config_revision_map, config_hash, acquisition_hash,
retry_count, max_retries, public_status_message, created_at, updated_at,
completed_at
"""

ACTIVE_BOOTSTRAP_STATUSES = (
    "not_started",
    "global_queued",
    "global_running",
    "global_succeeded",
    "personal_queued",
    "personal_running",
    "failed_retryable",
    "personal_failed_retryable",
)


def acquisition_config_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Extract only connector-relevant settings from an effective user snapshot."""

    configs = snapshot.get("configs") if isinstance(snapshot, dict) else {}
    jobs_config = configs.get("jobs_config") if isinstance(configs, dict) else {}
    if not isinstance(jobs_config, dict):
        return {}
    return {
        "global_filters": jobs_config.get("global_filters") or {},
        "job_categories": jobs_config.get("job_categories") or [],
    }


def stable_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class BootstrapRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()
        self.pipeline_runs = PipelineRunRepository(self.store)
        self.connector_runs = ConnectorRunRepository(self.store)

    def get_for_user(self, user_uuid: UUID | str) -> dict[str, Any]:
        row = self.store.fetch_one(
            f"""
            select {BOOTSTRAP_COLUMNS}
            from public.user_bootstrap_workflows
            where user_uuid = %s
            order by created_at desc
            limit 1
            """,
            [str(user_uuid)],
        )
        if row is None:
            return {"user_uuid": str(user_uuid), "status": "not_started"}
        return row

    def get_by_connector_run(self, connector_run_uuid: UUID | str) -> dict[str, Any] | None:
        return self.store.fetch_one(
            f"""
            select {BOOTSTRAP_COLUMNS}
            from public.user_bootstrap_workflows
            where connector_run_uuid = %s
            limit 1
            """,
            [str(connector_run_uuid)],
        )

    def is_completed(self, user_uuid: UUID | str) -> bool:
        row = self.store.fetch_one(
            """
            select 1
            from public.user_bootstrap_workflows
            where user_uuid = %s and status = 'completed'
            limit 1
            """,
            [str(user_uuid)],
        )
        return row is not None

    def _active_for_user(self, connection: Any, user_uuid: UUID | str) -> dict[str, Any] | None:
        return connection.execute(
            f"""
            select {BOOTSTRAP_COLUMNS}
            from public.user_bootstrap_workflows
            where user_uuid = %s
              and status in (
                  'not_started',
                  'global_queued',
                  'global_running',
                  'global_succeeded',
                  'personal_queued',
                  'personal_running',
                  'failed_retryable',
                  'personal_failed_retryable'
              )
            order by created_at
            for update
            limit 1
            """,
            [str(user_uuid)],
        ).fetchone()

    def _run_for_workflow(self, connection: Any, workflow: dict[str, Any]) -> dict[str, Any]:
        personal_run_uuid = workflow.get("personal_run_uuid")
        if not personal_run_uuid:
            raise NotFoundError("Bootstrap workflow has no personal run")
        run = connection.execute(
            f"""
            select {PUBLIC_RUN_COLUMNS}
            from public.user_pipeline_runs
            where user_uuid = %s and run_uuid = %s
            """,
            [str(workflow["user_uuid"]), str(personal_run_uuid)],
        ).fetchone()
        if run is None:
            raise NotFoundError("Bootstrap personal run was not found")
        output = dict(run)
        output["bootstrap_status"] = workflow["status"]
        output["connector_run_uuid"] = workflow.get("connector_run_uuid")
        return output

    def start_or_get(
        self,
        *,
        user_uuid: UUID | str,
        snapshot: dict[str, Any],
        daily_limit: int | None,
    ) -> dict[str, Any]:
        acquisition_config = acquisition_config_from_snapshot(snapshot)
        acquisition_hash = stable_hash(acquisition_config)
        with self.store.transaction() as connection:
            existing = self._active_for_user(connection, user_uuid)
            if existing is not None:
                return self._run_for_workflow(connection, existing)

            if daily_limit is not None:
                recent = connection.execute(
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
                workflow = connection.execute(
                    f"""
                    insert into public.user_bootstrap_workflows (
                        user_uuid, status, config_snapshot, config_revision_map,
                        config_hash, acquisition_hash, public_status_message
                    ) values (
                        %s, 'not_started', %s, %s, %s, %s,
                        'Preparing the first shared-data refresh.'
                    )
                    returning {BOOTSTRAP_COLUMNS}
                    """,
                    [
                        str(user_uuid),
                        Jsonb(snapshot),
                        Jsonb(snapshot.get("config_revision_map", {})),
                        snapshot["config_hash"],
                        acquisition_hash,
                    ],
                ).fetchone()
            except Exception as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    existing = self._active_for_user(connection, user_uuid)
                    if existing is not None:
                        return self._run_for_workflow(connection, existing)
                    raise PipelineAlreadyActiveError("A bootstrap workflow is already active") from exc
                raise

            personal_run = self.pipeline_runs.create(
                user_uuid=user_uuid,
                snapshot=snapshot,
                daily_limit=None,
                status="waiting_for_global",
                is_bootstrap_run=True,
                trigger_type="first_user_bootstrap",
                bootstrap_uuid=workflow["bootstrap_uuid"],
                connection=connection,
            )
            connector_run = self.connector_runs.create(
                trigger_type="first_user_bootstrap",
                initiating_user_uuid=user_uuid,
                bootstrap_uuid=workflow["bootstrap_uuid"],
                initiating_config_revision_map=snapshot.get("config_revision_map", {}),
                initiating_config_hash=snapshot["config_hash"],
                initiating_acquisition_hash=acquisition_hash,
                resulting_personal_run_uuid=personal_run["run_uuid"],
                connection=connection,
            )
            workflow = connection.execute(
                f"""
                update public.user_bootstrap_workflows
                set status = 'global_queued',
                    personal_run_uuid = %s,
                    connector_run_uuid = %s,
                    updated_at = now(),
                    public_status_message = 'Shared job-data refresh queued for your first run.'
                where bootstrap_uuid = %s
                returning {BOOTSTRAP_COLUMNS}
                """,
                [
                    personal_run["run_uuid"],
                    connector_run["connector_run_uuid"],
                    workflow["bootstrap_uuid"],
                ],
            ).fetchone()
            output = dict(personal_run)
            output["bootstrap_status"] = workflow["status"]
            output["connector_run_uuid"] = connector_run["connector_run_uuid"]
            return output

    def mark_global_running(self, *, connector_run_uuid: UUID | str) -> None:
        self.store.execute(
            """
            update public.user_bootstrap_workflows
            set status = 'global_running', updated_at = now(),
                public_status_message = 'Refreshing shared job data for your first run.'
            where connector_run_uuid = %s
              and status in ('global_queued', 'failed_retryable')
            """,
            [str(connector_run_uuid)],
        )

    def mark_global_succeeded(self, *, connector_run_uuid: UUID | str) -> dict[str, Any] | None:
        with self.store.transaction() as connection:
            workflow = connection.execute(
                f"""
                select {BOOTSTRAP_COLUMNS}
                from public.user_bootstrap_workflows
                where connector_run_uuid = %s
                for update
                """,
                [str(connector_run_uuid)],
            ).fetchone()
            if workflow is None:
                return None
            if workflow["status"] not in {"global_running", "global_queued", "failed_retryable"}:
                return dict(workflow)
            run = connection.execute(
                f"""
                update public.user_pipeline_runs
                set status = 'queued',
                    source_connector_run_uuid = %s
                where run_uuid = %s and status = 'waiting_for_global'
                returning {PUBLIC_RUN_COLUMNS}
                """,
                [str(connector_run_uuid), str(workflow["personal_run_uuid"])],
            ).fetchone()
            if run is None:
                raise InvalidStateTransitionError("Only waiting bootstrap runs may be queued")
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                    run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'global_refresh_completed',
                          'Shared job dataset refreshed; personal dbt run queued')
                """,
                [str(workflow["personal_run_uuid"]), workflow["user_uuid"]],
            )
            run = dict(run)
            updated = connection.execute(
                f"""
                update public.user_bootstrap_workflows
                set status = 'personal_queued', updated_at = now(),
                    public_status_message = 'Personal matching queued against the refreshed shared data.'
                where bootstrap_uuid = %s
                returning {BOOTSTRAP_COLUMNS}
                """,
                [workflow["bootstrap_uuid"]],
            ).fetchone()
            run["bootstrap_status"] = updated["status"]
            return run

    def mark_global_failed(
        self,
        *,
        connector_run_uuid: UUID | str,
        internal_error_message: str,
    ) -> None:
        self.store.execute(
            """
            update public.user_bootstrap_workflows
            set status = case
                    when retry_count + 1 >= max_retries then 'failed_terminal'
                    else 'failed_retryable'
                end,
                retry_count = retry_count + 1,
                updated_at = now(),
                public_status_message = 'The shared-data refresh failed. Your previous results remain unchanged.',
                internal_error_message = %s
            where connector_run_uuid = %s
            """,
            [internal_error_message[:8000], str(connector_run_uuid)],
        )

    def mark_personal_running(
        self,
        *,
        bootstrap_uuid: UUID | str,
        run_uuid: UUID | str,
    ) -> None:
        updated = self.store.execute(
            """
            update public.user_bootstrap_workflows
            set status = 'personal_running', updated_at = now(),
                public_status_message = 'Building your first personal matches.'
            where bootstrap_uuid = %s
              and personal_run_uuid = %s
              and status = 'personal_queued'
            """,
            [str(bootstrap_uuid), str(run_uuid)],
        )
        if updated == 0:
            raise InvalidStateTransitionError("Bootstrap workflow is not ready for personal execution")

    def mark_personal_completed(
        self,
        *,
        bootstrap_uuid: UUID | str,
        run_uuid: UUID | str,
    ) -> None:
        self.store.execute(
            """
            update public.user_bootstrap_workflows
            set status = 'completed',
                updated_at = now(),
                completed_at = now(),
                public_status_message = 'Your first personal refresh completed.'
            where bootstrap_uuid = %s
              and personal_run_uuid = %s
              and status = 'personal_running'
            """,
            [str(bootstrap_uuid), str(run_uuid)],
        )

    def mark_personal_failed(
        self,
        *,
        bootstrap_uuid: UUID | str,
        run_uuid: UUID | str,
        internal_error_message: str,
    ) -> None:
        self.store.execute(
            """
            update public.user_bootstrap_workflows
            set status = 'personal_failed_retryable',
                updated_at = now(),
                public_status_message = 'The shared refresh completed, but personal matching failed.',
                internal_error_message = %s
            where bootstrap_uuid = %s
              and personal_run_uuid = %s
            """,
            [internal_error_message[:8000], str(bootstrap_uuid), str(run_uuid)],
        )
