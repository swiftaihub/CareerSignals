"""Dedicated worker for queued, per-user dbt refreshes."""

from __future__ import annotations

import logging
import socket
import threading
import time
from typing import Any, Callable

from packages.careersignal_core.repositories.pipeline_runs import PipelineRunRepository
from packages.careersignal_core.settings import AppSettings, get_settings
from packages.careersignal_core.tasks.claim import claim_next_user_pipeline_run
from packages.careersignal_core.tasks.locks import AdvisoryLockManager, LockUnavailableError

LOGGER = logging.getLogger(__name__)


def worker_identity() -> str:
    return f"{socket.gethostname()}:{threading.get_native_id()}"


class UserPipelineWorker:
    def __init__(
        self,
        *,
        repository: PipelineRunRepository | None = None,
        locks: AdvisoryLockManager | None = None,
        settings: AppSettings | None = None,
        runner: Callable[..., dict[str, Any]] | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.repository = repository or PipelineRunRepository()
        self.locks = locks or AdvisoryLockManager()
        self.settings = settings or get_settings()
        self.runner = runner or self._default_runner
        self.worker_id = worker_id or worker_identity()

    @staticmethod
    def _default_runner(**kwargs: Any) -> dict[str, Any]:
        # Delayed import proves API composition never imports connectors/user runner code.
        from packages.careersignal_core.publication.user_results import UserResultsPublisher
        from src.pipelines.user_dbt_refresh import run_user_dbt_refresh

        return run_user_dbt_refresh(**kwargs, publisher=UserResultsPublisher())

    def process_one(self) -> bool:
        run = claim_next_user_pipeline_run(self.worker_id, self.repository)
        if run is None:
            return False
        user_uuid, run_uuid = str(run["user_uuid"]), str(run["run_uuid"])
        try:
            with self.locks.acquire(f"careersignals:user:{user_uuid}", wait=False):
                with self.locks.acquire_writer_slot(self.settings.user_pipeline_max_concurrency):
                    self.repository.add_event(
                        run_uuid=run_uuid,
                        user_uuid=user_uuid,
                        event_type="dbt_started",
                        message="Staging immutable configuration and building user models",
                    )
                    self.runner(
                        user_uuid=user_uuid,
                        run_uuid=run_uuid,
                        config_snapshot=dict(run["config_snapshot"]),
                    )
            return True
        except LockUnavailableError as exc:
            LOGGER.info("Requeueing user pipeline run %s: %s", run_uuid, exc)
            self.repository.requeue(
                run_uuid=run_uuid,
                reason="Pipeline is waiting for an available processing slot.",
            )
        except Exception as exc:  # worker boundary intentionally catches all task failures
            LOGGER.exception("User pipeline run %s failed", run_uuid)
            self.repository.fail(
                run_uuid=run_uuid,
                error_code="PIPELINE_EXECUTION_FAILED",
                public_message="The pipeline failed. Your previous results are still available.",
                internal_message=f"{type(exc).__name__}: {exc}",
            )
        return True

    def run_forever(self, stop_event: threading.Event | None = None) -> None:
        stop = stop_event or threading.Event()
        LOGGER.info("User pipeline worker %s started", self.worker_id)
        while not stop.is_set():
            processed = self.process_one()
            if not processed:
                stop.wait(self.settings.user_pipeline_poll_seconds)
