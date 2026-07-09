from pathlib import Path
import sys

from packages.careersignal_core.dbt.runner import _dbt_env, _dbt_executable, run_dbt
from packages.careersignal_core.settings import data_mode


def test_all_dbt_sql_models_have_incremental_config() -> None:
    model_paths = sorted(Path("dbt/models").rglob("*.sql"))

    assert model_paths
    for model_path in model_paths:
        sql = model_path.read_text(encoding="utf-8")
        assert "{{ config(" in sql, f"{model_path} is missing a model config block"
        assert "materialized='incremental'" in sql, f"{model_path} is not incremental"
        assert "incremental_strategy='delete+insert'" in sql, (
            f"{model_path} does not use delete+insert incremental strategy"
        )
        assert "unique_key=" in sql, f"{model_path} is missing a unique_key"


def test_motherduck_mode_routes_dbt_to_dev_target(monkeypatch) -> None:
    monkeypatch.setenv("CAREERSIGNAL_DATA_MODE", "motherduck")
    monkeypatch.setenv("DBT_TARGET", "local")

    env = _dbt_env()

    assert env["DBT_TARGET"] == "dev"


def test_default_data_mode_is_motherduck(monkeypatch) -> None:
    monkeypatch.delenv("CAREERSIGNAL_DATA_MODE", raising=False)

    assert data_mode() == "motherduck"


def test_dbt_runner_uses_current_python_environment_executable() -> None:
    expected = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")

    if expected.exists():
        assert _dbt_executable() == str(expected)


def test_dbt_runner_adds_full_refresh_flag(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, check, env):
        captured["command"] = command
        captured["check"] = check
        captured["env"] = env

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setenv("CAREERSIGNAL_DATA_MODE", "motherduck")
    monkeypatch.setenv("DBT_TARGET", "dev")

    run_dbt(tmp_path / "dbt", tmp_path / "profiles", full_refresh=True)

    command = captured["command"]
    assert isinstance(command, list)
    assert command[1:2] == ["run"]
    assert "--full-refresh" in command
    assert captured["check"] is True
