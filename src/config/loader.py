"""YAML configuration loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from src.config.schemas import (
    CandidateProfileConfig,
    ConfigBundle,
    JobsConfig,
    SkillTaxonomyConfig,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class ConfigLoadError(RuntimeError):
    """Raised when a CareerSignal configuration file cannot be loaded."""


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigLoadError(f"Configuration file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigLoadError(f"Expected a YAML mapping in {path}")
    return data


def _validate_model(model_cls: type[ModelT], data: dict[str, Any], path: Path) -> ModelT:
    try:
        if hasattr(model_cls, "model_validate"):
            return model_cls.model_validate(data)  # type: ignore[attr-defined]
        return model_cls.parse_obj(data)
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid configuration in {path}: {exc}") from exc


def load_configs(project_root: str | Path = ".") -> ConfigBundle:
    """Load and validate all CareerSignal YAML configuration files."""

    root = Path(project_root)
    config_dir = root / "config"

    jobs_path = config_dir / "jobs_config.yml"
    candidate_path = config_dir / "candidate_profile.yml"
    taxonomy_path = config_dir / "skill_taxonomy.yml"

    jobs = _validate_model(JobsConfig, _load_yaml(jobs_path), jobs_path)
    candidate_profile = _validate_model(
        CandidateProfileConfig, _load_yaml(candidate_path), candidate_path
    )
    skill_taxonomy = _validate_model(
        SkillTaxonomyConfig, _load_yaml(taxonomy_path), taxonomy_path
    )

    return ConfigBundle(
        jobs=jobs,
        candidate_profile=candidate_profile,
        skill_taxonomy=skill_taxonomy,
    )
