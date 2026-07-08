"""Subprocess runner for dbt commands."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess

from packages.careersignal_core.settings import data_mode


def _dbt_env() -> dict[str, str]:
    env = os.environ.copy()
    if data_mode() == "motherduck" and not env.get("DBT_TARGET"):
        env["DBT_TARGET"] = "dev"
    return env


def run_dbt(project_dir: str | Path, profiles_dir: str | Path) -> None:
    subprocess.run(
        ["dbt", "run", "--project-dir", str(project_dir), "--profiles-dir", str(profiles_dir)],
        check=True,
        env=_dbt_env(),
    )


def test_dbt(project_dir: str | Path, profiles_dir: str | Path) -> None:
    subprocess.run(
        ["dbt", "test", "--project-dir", str(project_dir), "--profiles-dir", str(profiles_dir)],
        check=True,
        env=_dbt_env(),
    )
