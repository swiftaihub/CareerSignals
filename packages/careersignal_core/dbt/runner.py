"""Subprocess runner for dbt commands."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from packages.careersignal_core.settings import bool_env, data_mode


def _dbt_env() -> dict[str, str]:
    env = os.environ.copy()
    target = env.get("DBT_TARGET", "").strip().casefold()
    if data_mode() == "motherduck" and target in {"", "local"}:
        env["DBT_TARGET"] = "dev"
    return env


def _dbt_executable() -> str:
    executable_name = "dbt.exe" if os.name == "nt" else "dbt"
    sibling_executable = Path(sys.executable).with_name(executable_name)
    if sibling_executable.exists():
        return str(sibling_executable)
    return "dbt"


def run_dbt(
    project_dir: str | Path,
    profiles_dir: str | Path,
    full_refresh: bool | None = None,
) -> None:
    command = [
        _dbt_executable(),
        "run",
        "--project-dir",
        str(project_dir),
        "--profiles-dir",
        str(profiles_dir),
    ]
    should_full_refresh = (
        full_refresh if full_refresh is not None else bool_env("CAREERSIGNAL_DBT_FULL_REFRESH")
    )
    if should_full_refresh:
        command.append("--full-refresh")

    subprocess.run(
        command,
        check=True,
        env=_dbt_env(),
    )


def test_dbt(project_dir: str | Path, profiles_dir: str | Path) -> None:
    subprocess.run(
        [
            _dbt_executable(),
            "test",
            "--project-dir",
            str(project_dir),
            "--profiles-dir",
            str(profiles_dir),
        ],
        check=True,
        env=_dbt_env(),
    )
