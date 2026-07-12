from __future__ import annotations

from types import SimpleNamespace

from packages.careersignal_core.repositories.errors import ConflictError
from scripts import refresh_connectors


class FakeRepository:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.calls = []

    def create_if_no_active(self, **kwargs):
        self.calls.append(kwargs)
        if self.conflict:
            raise ConflictError("active")
        return {
            "connector_run_uuid": "22222222-2222-4222-8222-222222222222",
            "status": "queued",
            "trigger_type": kwargs["trigger_type"],
        }


def _patch_settings(monkeypatch) -> None:
    settings = SimpleNamespace(require_api_configuration=lambda: None)
    monkeypatch.setattr(refresh_connectors, "get_settings", lambda: settings)
    monkeypatch.setattr(refresh_connectors, "configure_logging", lambda: None)


def test_cli_enqueues_manual_cli_and_prints_uuid(monkeypatch, capsys) -> None:
    _patch_settings(monkeypatch)
    repository = FakeRepository()

    exit_code = refresh_connectors.main(["--enqueue"], repository=repository)

    output = capsys.readouterr()
    assert exit_code == 0
    assert repository.calls == [{"trigger_type": "manual_cli", "scheduled_for": None, "next_scheduled_at": None}]
    assert "22222222-2222-4222-8222-222222222222" in output.out
    assert "python -m apps.worker.main" in output.out


def test_cli_overlap_exits_nonzero(monkeypatch, capsys) -> None:
    _patch_settings(monkeypatch)

    exit_code = refresh_connectors.main([], repository=FakeRepository(conflict=True))

    assert exit_code != 0
    assert "already queued or running" in capsys.readouterr().err


def test_cli_enqueue_mode_does_not_import_or_execute_pipeline(monkeypatch) -> None:
    _patch_settings(monkeypatch)
    assert not hasattr(refresh_connectors, "run_shared_connector_refresh")

    assert refresh_connectors.main([], repository=FakeRepository()) == 0
