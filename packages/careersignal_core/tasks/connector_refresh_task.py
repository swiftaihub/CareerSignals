"""Trusted scheduled entrypoint for global connector refresh."""

from __future__ import annotations

import logging
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
) -> dict[str, Any]:
    """Create global refresh metadata for the worker without doing HTTP work."""

    repo = repository or ConnectorRunRepository()
    try:
        return repo.create_if_no_active(trigger_type=trigger_type)
    except ConflictError:
        LOGGER.info("A global connector refresh is already queued or running")
        return {"status": "skipped", "reason": "global_refresh_already_active"}
