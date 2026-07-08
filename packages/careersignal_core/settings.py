"""Environment-driven settings for CareerSignal services."""

from __future__ import annotations

import os
from pathlib import Path


def data_mode() -> str:
    """Return the configured data mode: local or motherduck."""

    value = os.getenv("CAREERSIGNAL_DATA_MODE", "local").strip().casefold()
    return value if value in {"local", "motherduck"} else "local"


def is_motherduck_mode() -> bool:
    return data_mode() == "motherduck"


def bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_project_path(path: str | Path) -> Path:
    """Resolve repo-relative or apps/api-relative paths to an absolute path."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    root = project_root()
    root_candidate = (root / candidate).resolve()
    if root_candidate.exists():
        return root_candidate

    api_candidate = (root / "apps" / "api" / candidate).resolve()
    if api_candidate.exists():
        return api_candidate

    return root_candidate


def local_data_dir() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_LOCAL_DATA_DIR", "data"))


def output_dir() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_OUTPUT_DIR", "outputs"))


def excel_path() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_EXCEL_PATH", "outputs/job_search_tracker.xlsx"))


def dbt_project_dir() -> Path:
    return resolve_project_path(os.getenv("DBT_PROJECT_DIR", "dbt"))


def dbt_profiles_dir() -> Path:
    return resolve_project_path(os.getenv("DBT_PROFILES_DIR", "dbt"))
