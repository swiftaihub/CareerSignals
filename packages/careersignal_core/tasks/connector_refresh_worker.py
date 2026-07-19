"""Worker for queued system-owned global connector refreshes."""

from __future__ import annotations

import logging
from pathlib import Path
import threading
from typing import Any, Callable

from packages.careersignal_core.repositories.bootstrap import BootstrapRepository
from packages.careersignal_core.repositories.configs import ConfigRepository
from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.settings import AppSettings, get_settings
from packages.careersignal_core.tasks.locks import AdvisoryLockManager, LockUnavailableError

LOGGER = logging.getLogger(__name__)


class ConnectorRefreshWorker:
    def __init__(
        self,
        *,
        repository: ConnectorRunRepository | None = None,
        config_repository: ConfigRepository | None = None,
        bootstrap_repository: BootstrapRepository | None = None,
        locks: AdvisoryLockManager | None = None,
        settings: AppSettings | None = None,
        runner: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.repository = repository or ConnectorRunRepository()
        self.config_repository = config_repository or ConfigRepository()
        self.bootstrap_repository = bootstrap_repository or BootstrapRepository()
        self.locks = locks or AdvisoryLockManager()
        self.settings = settings or get_settings()
        self.runner = runner or self._default_runner

    @staticmethod
    def _default_runner(**kwargs: Any) -> dict[str, Any]:
        from packages.careersignal_core.publication.shared_jobs import SharedJobsPublisher
        from src.pipelines.shared_connector_refresh import run_shared_connector_refresh

        return run_shared_connector_refresh(**kwargs, publisher=SharedJobsPublisher())

    def _snapshots_for_run(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        snapshots = self.config_repository.active_user_snapshots()
        if run.get("trigger_type") != "first_user_bootstrap":
            return snapshots

        workflow = self.bootstrap_repository.get_by_connector_run(run["connector_run_uuid"])
        if workflow is None:
            return snapshots
        user_uuid = str(workflow["user_uuid"])
        if not self.config_repository.is_eligible_for_global_refresh(user_uuid):
            LOGGER.warning("Bootstrap user %s is no longer eligible for global refresh", user_uuid)
            return [item for item in snapshots if str(item.get("user_uuid")) != user_uuid]
        frozen_snapshot = dict(workflow.get("config_snapshot") or {})
        frozen_snapshot["user_uuid"] = user_uuid
        return [
            item for item in snapshots if str(item.get("user_uuid")) != user_uuid
        ] + [frozen_snapshot]

    def recover_stale_runs(self) -> int:
        recovered = self.repository.fail_stale_running(
            max_age_seconds=self.settings.connector_refresh_max_seconds,
        )
        if recovered:
            LOGGER.warning("Marked %s orphaned connector refresh run(s) as failed", recovered)
        return recovered

    def process_one(self) -> bool:
        run = self.repository.claim_next()
        if run is None:
            return False
        run_uuid = str(run["connector_run_uuid"])
        try:
            with self.locks.acquire("careersignals:global-connector-refresh", wait=False):
                if run.get("trigger_type") == "first_user_bootstrap":
                    self.bootstrap_repository.mark_global_running(
                        connector_run_uuid=run_uuid,
                    )
                user_snapshots = self._snapshots_for_run(run)
                from src.config.loader import load_configs
                from src.pipelines.shared_connector_refresh import (
                    build_acquisition_inputs,
                    build_acquisition_query_plan,
                    source_names_from_config,
                )

                configs = load_configs(Path.cwd())
                filters, categories, acquisition_metadata = build_acquisition_inputs(
                    configs, user_snapshots
                )
                acquisition_queries = build_acquisition_query_plan(
                    source_names=source_names_from_config(configs),
                    configs=configs,
                    global_filters=filters,
                    categories=categories,
                    user_snapshots=user_snapshots,
                )
                self.repository.record_acquisition_audit(
                    connector_run_uuid=run_uuid,
                    user_snapshots=list(acquisition_metadata.get("user_snapshots") or []),
                    acquisition_queries=acquisition_queries,
                )
                with self.locks.acquire_writer_slot(
                    self.settings.user_pipeline_max_concurrency
                ):
                    result = self.runner(
                        connector_run_uuid=run_uuid,
                        user_snapshots=user_snapshots,
                    )
                acquisition = result.get("acquisition") or {}
                self.repository.record_acquisition_audit(
                    connector_run_uuid=run_uuid,
                    user_snapshots=list(acquisition.get("user_snapshots") or []),
                    acquisition_queries=list(acquisition.get("queries") or []),
                )
                for source in result.get("source_results", []):
                    self.repository.upsert_source_result(
                        connector_run_uuid=run_uuid,
                        source_name=str(source["source_name"]),
                        status=str(source["status"]),
                        records_fetched=int(source.get("records_fetched", 0)),
                        records_retained=int(source.get("records_retained", 0)),
                        public_status_message=str(source.get("public_status_message", "")),
                        internal_error_message=source.get("internal_error_message"),
                    )
                status = str(result.get("status", "completed"))
                shared_dbt_completed = bool(
                    result.get("shared_dbt_run_completed", result.get("dbt_completed", False))
                )
                self.repository.finish(
                    connector_run_uuid=run_uuid,
                    status=status,
                    jobs_fetched=int(result.get("jobs_fetched", result.get("fetched_raw_jobs", 0))),
                    jobs_retained=int(result.get("jobs_retained", result.get("shared_jobs", 0))),
                    jobs_published=int(result.get("jobs_published", result.get("published_jobs", 0))),
                    shared_dbt_run_completed=shared_dbt_completed,
                    public_status_message=str(result.get("public_status_message", "Updated successfully")),
                )
                LOGGER.info(
                    "Global connector refresh finished",
                    extra={
                        "connector_run_uuid": run_uuid,
                        "trigger_type": run.get("trigger_type"),
                        "scheduled_for": run.get("scheduled_for"),
                        "next_scheduled_at": run.get("next_scheduled_at"),
                        "execution_status": status,
                    },
                )
                if run.get("trigger_type") == "first_user_bootstrap":
                    if status in {"completed", "partial"} and shared_dbt_completed:
                        self.bootstrap_repository.mark_global_succeeded(
                            connector_run_uuid=run_uuid,
                        )
                    else:
                        self.bootstrap_repository.mark_global_failed(
                            connector_run_uuid=run_uuid,
                            internal_error_message="Shared refresh did not publish successfully",
                        )
            return True
        except LockUnavailableError as exc:
            LOGGER.info("Global connector refresh %s could not acquire lock: %s", run_uuid, exc)
            self.repository.requeue(
                run_uuid,
                public_status_message="Waiting for another shared-data refresh to finish.",
            )
        except Exception as exc:
            error_type = type(exc).__name__
            internal_message = f"{error_type}: Global connector refresh failed."
            LOGGER.error("Global connector refresh %s failed (%s)", run_uuid, error_type)
            self.repository.finish(
                connector_run_uuid=run_uuid,
                status="failed",
                jobs_fetched=0,
                jobs_retained=0,
                jobs_published=0,
                shared_dbt_run_completed=False,
                public_status_message="The shared-data refresh was not completed.",
                error_code="CONNECTOR_REFRESH_FAILED",
                internal_error_message=internal_message,
            )
            LOGGER.error(
                "Global connector refresh recorded as failed",
                extra={
                    "connector_run_uuid": run_uuid,
                    "trigger_type": run.get("trigger_type"),
                    "scheduled_for": run.get("scheduled_for"),
                    "next_scheduled_at": run.get("next_scheduled_at"),
                    "execution_status": "failed",
                },
            )
            if run.get("trigger_type") == "first_user_bootstrap":
                self.bootstrap_repository.mark_global_failed(
                    connector_run_uuid=run_uuid,
                    internal_error_message=internal_message,
                )
        return True

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop = stop_event or threading.Event()
        self.recover_stale_runs()
        LOGGER.info("Global connector refresh worker started")
        while not stop.is_set():
            processed = self.process_one()
            if not processed:
                stop.wait(self.settings.user_pipeline_poll_seconds)
