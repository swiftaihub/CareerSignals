from pathlib import Path
import sys

from packages.careersignal_core.dbt.runner import _dbt_env, _dbt_executable
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


def test_dbt_project_defines_fixed_shared_and_user_selectors() -> None:
    selectors = Path("dbt/selectors.yml").read_text(encoding="utf-8")

    assert "name: shared_refresh" in selectors
    assert "name: user_refresh" in selectors
