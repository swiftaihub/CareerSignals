"""Trusted scheduled entrypoint for global connector refresh."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.errors import ConflictError
from packages.careersignal_core.settings import AppSettings, get_settings
from packages.careersignal_core.tasks.connector_refresh_worker import ConnectorRefreshWorker
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
    worker = ConnectorRefreshWorker(
        repository=repo,
        locks=lock_manager,
        settings=process_settings,
        runner=runner or _default_runner,
    )
    worker.process_one()
    completed = repo.get(run["connector_run_uuid"]) or run
    return {"connector_run_uuid": str(run["connector_run_uuid"]), **completed}


def enqueue_scheduled_connector_refresh(
    *,
    repository: ConnectorRunRepository | None = None,
    trigger_type: str = "scheduled",
    scheduled_for: datetime | None = None,
    next_scheduled_at: datetime | None = None,
) -> dict[str, Any]:
    """Create global refresh metadata for the worker without doing HTTP work."""

    try:
        run = enqueue_connector_refresh(
            repository=repository,
            trigger_type=trigger_type,
            scheduled_for=scheduled_for,
            next_scheduled_at=next_scheduled_at,
        )
        LOGGER.info(
            "Enqueued global connector refresh",
            extra={
                "connector_run_uuid": str(run["connector_run_uuid"]),
                "trigger_type": trigger_type,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "next_scheduled_at": next_scheduled_at.isoformat() if next_scheduled_at else None,
                "execution_status": run.get("status"),
            },
        )
        return run
    except ConflictError:
        LOGGER.info(
            "A global connector refresh is already queued or running",
            extra={
                "trigger_type": trigger_type,
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
                "next_scheduled_at": next_scheduled_at.isoformat() if next_scheduled_at else None,
                "execution_status": "skipped",
            },
        )
        return {"status": "skipped", "reason": "global_refresh_already_active"}


def enqueue_connector_refresh(
    *,
    repository: ConnectorRunRepository | None = None,
    trigger_type: str,
    scheduled_for: datetime | None = None,
    next_scheduled_at: datetime | None = None,
) -> dict[str, Any]:
    """Enqueue one global run, preserving conflicts for interactive callers."""

    repo = repository or ConnectorRunRepository()
    return repo.create_if_no_active(
        trigger_type=trigger_type,
        scheduled_for=scheduled_for,
        next_scheduled_at=next_scheduled_at,
    )
