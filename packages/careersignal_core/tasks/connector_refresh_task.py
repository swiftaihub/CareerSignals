"""Trusted scheduled entrypoint for global connector refresh."""

from __future__ import annotations

import logging
from typing import Any, Callable

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.settings import AppSettings, get_settings
from packages.careersignal_core.tasks.locks import AdvisoryLockManager

LOGGER = logging.getLogger(__name__)


def _default_runner(**kwargs: Any) -> dict[str, Any]:
    from packages.careersignal_core.publication.shared_jobs import SharedJobsPublisher
    from src.pipelines.shared_connector_refresh import run_shared_connector_refresh

    return run_shared_connector_refresh(**kwargs, publisher=SharedJobsPublisher())


def run_scheduled_connector_refresh(
    *,
    repository: ConnectorRunRepository | None = None,
    locks: AdvisoryLockManager | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
    settings: AppSettings | None = None,
    trigger_type: str = "scheduled",
) -> dict[str, Any]:
    repo = repository or ConnectorRunRepository()
    lock_manager = locks or AdvisoryLockManager()
    process_settings = settings or get_settings()
    run = repo.create(trigger_type=trigger_type)
    run_uuid = str(run["connector_run_uuid"])
    try:
        with lock_manager.acquire("careersignals:global-connector-refresh", wait=False):
            with lock_manager.acquire_writer_slot(
                process_settings.user_pipeline_max_concurrency
            ):
                repo.start(run_uuid)
                result = (runner or _default_runner)(connector_run_uuid=run_uuid)
            for source in result.get("source_results", []):
                repo.upsert_source_result(
                    connector_run_uuid=run_uuid,
                    source_name=str(source["source_name"]),
                    status=str(source["status"]),
                    records_fetched=int(source.get("records_fetched", 0)),
                    records_retained=int(source.get("records_retained", 0)),
                    public_status_message=str(source.get("public_status_message", "")),
                    internal_error_message=source.get("internal_error_message"),
                )
            repo.finish(
                connector_run_uuid=run_uuid,
                status=result.get("status", "completed"),
                jobs_fetched=int(result.get("jobs_fetched", result.get("fetched_raw_jobs", 0))),
                jobs_retained=int(result.get("jobs_retained", result.get("shared_jobs", 0))),
                jobs_published=int(result.get("jobs_published", result.get("published_jobs", 0))),
                shared_dbt_run_completed=bool(
                    result.get("shared_dbt_run_completed", result.get("dbt_completed", False))
                ),
                public_status_message=str(result.get("public_status_message", "Updated successfully")),
            )
            return {"connector_run_uuid": run_uuid, **result}
    except Exception as exc:
        LOGGER.exception("Global connector refresh %s failed", run_uuid)
        repo.finish(
            connector_run_uuid=run_uuid,
            status="failed",
            jobs_fetched=0,
            jobs_retained=0,
            jobs_published=0,
            shared_dbt_run_completed=False,
            public_status_message="The scheduled refresh was not completed.",
            error_code="CONNECTOR_REFRESH_FAILED",
            internal_error_message=f"{type(exc).__name__}: {exc}",
        )
        raise
