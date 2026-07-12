from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Iterator

from packages.careersignal_core.tasks.user_pipeline_worker import UserPipelineWorker


USER_UUID = "11111111-1111-4111-8111-111111111111"
RUN_UUID = "22222222-2222-4222-8222-222222222222"
CONNECTOR_RUN_UUID = "33333333-3333-4333-8333-333333333333"
BOOTSTRAP_UUID = "44444444-4444-4444-8444-444444444444"


class FakeRepository:
    def __init__(self, *, bootstrap: bool = False, source: str | None = CONNECTOR_RUN_UUID) -> None:
        self.claimed = False
        self.bootstrap = bootstrap
        self.source = source
        self.events: list[str] = []
        self.requeued: list[str] = []
        self.failed: list[str] = []

    def claim_next(self, worker_id: str) -> dict[str, Any] | None:
        if self.claimed:
            return None
        self.claimed = True
        return {
            "user_uuid": USER_UUID,
            "run_uuid": RUN_UUID,
            "config_snapshot": {"config_hash": "hash"},
            "source_connector_run_uuid": self.source,
            "bootstrap_uuid": BOOTSTRAP_UUID if self.bootstrap else None,
        }

    def add_event(
        self,
        *,
        run_uuid: str,
        user_uuid: str,
        event_type: str,
        message: str,
        level: str = "info",
    ) -> None:
        self.events.append(event_type)

    def requeue(self, *, run_uuid: str, reason: str) -> None:
        self.requeued.append(reason)

    def fail(
        self,
        *,
        run_uuid: str,
        error_code: str,
        public_message: str,
        internal_message: str,
    ) -> None:
        self.failed.append(internal_message)


class FakeBootstrapRepository:
    def __init__(self) -> None:
        self.transitions: list[str] = []

    def mark_personal_running(self, **kwargs: Any) -> None:
        self.transitions.append("personal_running")

    def mark_personal_completed(self, **kwargs: Any) -> None:
        self.transitions.append("completed")

    def mark_personal_failed(self, **kwargs: Any) -> None:
        self.transitions.append("personal_failed")


class FakeLocks:
    @contextmanager
    def acquire(self, name: str, *, wait: bool = True) -> Iterator[None]:
        yield

    @contextmanager
    def acquire_writer_slot(self, max_concurrency: int) -> Iterator[None]:
        yield


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        user_pipeline_max_concurrency=1,
        user_pipeline_poll_seconds=0.25,
    )


def test_worker_runs_only_user_dbt_with_bound_shared_version() -> None:
    repository = FakeRepository()
    bootstrap = FakeBootstrapRepository()
    calls: list[dict[str, Any]] = []

    def user_refresh(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"dbt_completed": True}

    worker = UserPipelineWorker(
        repository=repository,
        locks=FakeLocks(),
        settings=_settings(),
        runner=user_refresh,
        bootstrap_repository=bootstrap,
        worker_id="test-worker",
    )

    assert worker.process_one() is True
    assert len(calls) == 1
    assert calls[0]["user_uuid"] == USER_UUID
    assert calls[0]["run_uuid"] == RUN_UUID
    assert calls[0]["source_connector_run_uuid"] == CONNECTOR_RUN_UUID
    assert repository.events == ["dbt_started"]
    assert repository.failed == []
    assert bootstrap.transitions == []


def test_bootstrap_personal_failure_does_not_trigger_connectors() -> None:
    repository = FakeRepository(bootstrap=True)
    bootstrap = FakeBootstrapRepository()

    def user_refresh(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("dbt exploded")

    worker = UserPipelineWorker(
        repository=repository,
        locks=FakeLocks(),
        settings=_settings(),
        runner=user_refresh,
        bootstrap_repository=bootstrap,
        worker_id="test-worker",
    )

    assert worker.process_one() is True
    assert repository.events == ["dbt_started"]
    assert "RuntimeError: dbt exploded" in repository.failed[0]
    assert bootstrap.transitions == ["personal_running", "personal_failed"]


def test_unbound_personal_run_fails_before_user_dbt() -> None:
    repository = FakeRepository(source=None)
    calls: list[str] = []

    worker = UserPipelineWorker(
        repository=repository,
        locks=FakeLocks(),
        settings=_settings(),
        runner=lambda **kwargs: calls.append("user") or {"dbt_completed": True},
        bootstrap_repository=FakeBootstrapRepository(),
        worker_id="test-worker",
    )

    assert worker.process_one() is True
    assert calls == []
    assert "not bound to a successful shared refresh" in repository.failed[0]
