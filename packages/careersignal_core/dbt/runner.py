"""Safe subprocess runners for fixed CareerSignals dbt selectors."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence
from uuid import UUID

from packages.careersignal_core.settings import (
    data_mode,
    dbt_profiles_dir,
    dbt_project_dir,
)

SHARED_SELECTOR = "shared_refresh"
USER_SELECTOR = "user_refresh"


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


def _resolved_paths(
    project_dir: str | Path | None,
    profiles_dir: str | Path | None,
) -> tuple[Path, Path]:
    return (
        Path(project_dir) if project_dir is not None else dbt_project_dir(),
        Path(profiles_dir) if profiles_dir is not None else dbt_profiles_dir(),
    )


def _validate_uuid(value: str | UUID, name: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{name} must be a valid UUID") from exc


def _run_dbt_command(
    args: Sequence[str],
    *,
    project_dir: str | Path | None = None,
    profiles_dir: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    project, profiles = _resolved_paths(project_dir, profiles_dir)
    command = [
        _dbt_executable(),
        *args,
        "--project-dir",
        str(project),
        "--profiles-dir",
        str(profiles),
    ]
    return subprocess.run(
        command,
        check=True,
        env=_dbt_env(),
        text=True,
    )


def run_shared_dbt_build(
    project_dir: str | Path | None = None,
    profiles_dir: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Build and test only platform-shared dbt resources."""

    return _run_dbt_command(
        ["build", "--selector", SHARED_SELECTOR],
        project_dir=project_dir,
        profiles_dir=profiles_dir,
    )


def run_user_dbt_build(
    user_uuid: str | UUID,
    run_uuid: str | UUID,
    project_dir: str | Path | None = None,
    profiles_dir: str | Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Build and test one immutable user/run partition with a fixed selector."""

    user = _validate_uuid(user_uuid, "user_uuid")
    run = _validate_uuid(run_uuid, "run_uuid")
    variables = json.dumps(
        {"user_uuid": user, "run_uuid": run},
        sort_keys=True,
        separators=(",", ":"),
    )
    return _run_dbt_command(
        ["build", "--selector", USER_SELECTOR, "--vars", variables],
        project_dir=project_dir,
        profiles_dir=profiles_dir,
    )


def run_dbt(
    project_dir: str | Path,
    profiles_dir: str | Path,
    full_refresh: bool | None = None,
) -> subprocess.CompletedProcess[str]:
    """Compatibility wrapper for the old operational endpoint.

    It can no longer issue a project-wide full refresh and always resolves to
    the trusted shared selector. User execution must call
    :func:`run_user_dbt_build` with server-derived UUIDs.
    """

    if full_refresh:
        raise ValueError("Project-wide dbt --full-refresh is disabled")
    return run_shared_dbt_build(project_dir, profiles_dir)


def test_dbt(
    project_dir: str | Path,
    profiles_dir: str | Path,
) -> subprocess.CompletedProcess[str]:
    """Compatibility test command restricted to shared resources."""

    return _run_dbt_command(
        ["test", "--selector", SHARED_SELECTOR],
        project_dir=project_dir,
        profiles_dir=profiles_dir,
    )
