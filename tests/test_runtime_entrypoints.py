from __future__ import annotations

from types import SimpleNamespace

from apps.scheduler import main as scheduler_main
from apps.worker import main as worker_main


class CapturingHeartbeat:
    entered = 0
    exited = 0

    def __enter__(self):
        self.__class__.entered += 1
        return self

    def __exit__(self, *_exc_info):
        self.__class__.exited += 1


class AlreadyStoppedEvent:
    def is_set(self) -> bool:
        return True


def _reset_heartbeat() -> None:
    CapturingHeartbeat.entered = 0
    CapturingHeartbeat.exited = 0


def test_worker_main_uses_worker_validation_and_heartbeat(monkeypatch) -> None:
    _reset_heartbeat()
    validations: list[str] = []
    runtime_checks: list[str] = []
    settings = SimpleNamespace(
        require_worker_configuration=lambda: validations.append("worker"),
        log_level="INFO",
        user_pipeline_poll_seconds=2.0,
    )
    monkeypatch.setattr(worker_main, "get_settings", lambda: settings)
    monkeypatch.setattr(
        worker_main.FileHeartbeat,
        "from_environment",
        lambda: CapturingHeartbeat(),
    )
    monkeypatch.setattr(worker_main.threading, "Event", AlreadyStoppedEvent)
    monkeypatch.setattr(
        worker_main,
        "verify_worker_runtime",
        lambda: runtime_checks.append("motherduck"),
    )
    recoveries: list[str] = []
    connector_worker = SimpleNamespace(
        recover_stale_runs=lambda: recoveries.append("connectors"),
        process_one=lambda: False,
    )
    monkeypatch.setattr(worker_main, "ConnectorRefreshWorker", lambda **_kwargs: connector_worker)
    monkeypatch.setattr(worker_main, "UserPipelineWorker", lambda **_kwargs: object())

    worker_main.main()

    assert validations == ["worker"]
    assert runtime_checks == ["motherduck"]
    assert recoveries == ["connectors"]
    assert (CapturingHeartbeat.entered, CapturingHeartbeat.exited) == (1, 1)


def test_worker_runtime_requires_a_successful_motherduck_query(monkeypatch) -> None:
    statements: list[str] = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_exc_info):
            return None

        def execute(self, statement: str):
            statements.append(statement)
            return self

        @staticmethod
        def fetchone():
            return (1,)

    monkeypatch.setattr(
        worker_main,
        "MotherDuckService",
        lambda: SimpleNamespace(connect=Connection),
    )

    worker_main.verify_worker_runtime()

    assert statements == ["select 1"]


def test_scheduler_main_uses_scheduler_validation_and_heartbeat(monkeypatch) -> None:
    _reset_heartbeat()
    validations: list[str] = []
    starts: list[str] = []
    settings = SimpleNamespace(
        require_scheduler_configuration=lambda: validations.append("scheduler"),
        log_level="INFO",
    )
    scheduler = SimpleNamespace(start=lambda: starts.append("started"))
    monkeypatch.setattr(scheduler_main, "get_settings", lambda: settings)
    monkeypatch.setattr(scheduler_main, "build_scheduler", lambda: scheduler)
    monkeypatch.setattr(
        scheduler_main.FileHeartbeat,
        "from_environment",
        lambda: CapturingHeartbeat(),
    )

    scheduler_main.main()

    assert validations == ["scheduler"]
    assert starts == ["started"]
    assert (CapturingHeartbeat.entered, CapturingHeartbeat.exited) == (1, 1)
