from __future__ import annotations

import json

import pytest

from packages.careersignal_core.dbt import runner

USER_UUID = "11111111-1111-4111-8111-111111111111"
RUN_UUID = "22222222-2222-4222-8222-222222222222"
CONNECTOR_RUN_UUID = "33333333-3333-4333-8333-333333333333"


def _capture(monkeypatch):
    captured: list[str] = []

    def fake_run(command, **kwargs):
        captured.extend(command)
        return object()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    return captured


def test_shared_runner_uses_only_fixed_selector(monkeypatch, tmp_path) -> None:
    command = _capture(monkeypatch)

    runner.run_shared_dbt_build(tmp_path / "project", tmp_path / "profiles")

    assert command[1:4] == ["build", "--selector", "shared_refresh"]
    assert "--full-refresh" not in command


def test_user_runner_uses_fixed_selector_and_server_context(monkeypatch, tmp_path) -> None:
    command = _capture(monkeypatch)

    runner.run_user_dbt_build(
        USER_UUID,
        RUN_UUID,
        CONNECTOR_RUN_UUID,
        tmp_path / "project",
        tmp_path / "profiles",
    )

    assert command[1:4] == ["build", "--selector", "user_refresh"]
    variables = json.loads(command[command.index("--vars") + 1])
    assert variables == {
        "connector_run_uuid": CONNECTOR_RUN_UUID,
        "run_uuid": RUN_UUID,
        "user_uuid": USER_UUID,
    }
    assert "--full-refresh" not in command


def test_user_runner_rejects_non_uuid_context(monkeypatch) -> None:
    _capture(monkeypatch)

    with pytest.raises(ValueError, match="user_uuid"):
        runner.run_user_dbt_build("user-controlled-selector", RUN_UUID, CONNECTOR_RUN_UUID)


def test_user_runner_rejects_non_uuid_connector_context(monkeypatch) -> None:
    _capture(monkeypatch)

    with pytest.raises(ValueError, match="connector_run_uuid"):
        runner.run_user_dbt_build(USER_UUID, RUN_UUID, "browser-value")


def test_legacy_runner_rejects_full_refresh(monkeypatch, tmp_path) -> None:
    _capture(monkeypatch)

    with pytest.raises(ValueError, match="full-refresh"):
        runner.run_dbt(tmp_path, tmp_path, full_refresh=True)
