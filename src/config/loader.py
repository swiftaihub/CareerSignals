"""Safe repository-default and per-user override configuration loading."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from src.config.schemas import (
    CandidateProfileConfig,
    ConfigBundle,
    EffectiveUserConfig,
    LegacyJobsConfig,
    PlatformConnectorConfig,
    SkillTaxonomyConfig,
    UserJobsConfig,
)

ModelT = TypeVar("ModelT", bound=BaseModel)

CONFIG_TYPES: tuple[str, ...] = (
    "candidate_profile",
    "jobs_config",
    "skill_taxonomy",
)
_CONFIG_FILES = {
    "candidate_profile": "candidate_profile.yml",
    "jobs_config": "jobs_config.yml",
    "skill_taxonomy": "skill_taxonomy.yml",
}
_CONFIG_MODELS: dict[str, type[BaseModel]] = {
    "candidate_profile": CandidateProfileConfig,
    "jobs_config": UserJobsConfig,
    "skill_taxonomy": SkillTaxonomyConfig,
}
_USER_JOBS_KEYS = frozenset(UserJobsConfig.model_fields)
MAX_YAML_BYTES = 256 * 1024
MAX_CONFIG_DEPTH = 20


class ConfigLoadError(RuntimeError):
    """Raised when a CareerSignals configuration document is unsafe or invalid."""


def _root(project_root: str | Path | None) -> Path:
    return Path(project_root or Path(__file__).resolve().parents[2]).resolve()


def _depth(value: Any, current: int = 0) -> int:
    if current > MAX_CONFIG_DEPTH:
        return current
    if isinstance(value, Mapping):
        return max((_depth(item, current + 1) for item in value.values()), default=current)
    if isinstance(value, list):
        return max((_depth(item, current + 1) for item in value), default=current)
    return current


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigLoadError(f"Configuration file not found: {path}")
    if path.stat().st_size > MAX_YAML_BYTES:
        raise ConfigLoadError(f"Configuration file exceeds {MAX_YAML_BYTES} bytes: {path}")
    try:
        text = path.read_text(encoding="utf-8")
        # SafeLoader rejects Python/custom object tags.  Alias count limits the
        # practical expansion surface before the explicit depth check below.
        if text.count("*") > 50 or text.count("&") > 50:
            raise ConfigLoadError(f"Configuration contains too many YAML aliases: {path}")
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigLoadError(f"Expected a YAML mapping in {path}")
    if _depth(data) > MAX_CONFIG_DEPTH:
        raise ConfigLoadError(f"Configuration nesting exceeds {MAX_CONFIG_DEPTH} levels: {path}")
    return data


def _model_dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", round_trip=True)


def _validate_model(
    model_cls: type[ModelT], data: Mapping[str, Any], source: str | Path
) -> ModelT:
    try:
        return model_cls.model_validate(deepcopy(dict(data)))
    except ValidationError as exc:
        raise ConfigLoadError(f"Invalid configuration in {source}: {exc}") from exc


def _require_config_type(config_type: str) -> str:
    normalized = str(config_type).strip()
    if normalized not in CONFIG_TYPES:
        raise ConfigLoadError(
            f"Unsupported config type {config_type!r}; expected one of {', '.join(CONFIG_TYPES)}"
        )
    return normalized


def load_default_config(
    config_type: str, project_root: str | Path | None = None
) -> dict[str, Any]:
    """Load one validated repository user-default document as normalized JSON."""

    normalized_type = _require_config_type(config_type)
    path = _root(project_root) / "config" / _CONFIG_FILES[normalized_type]
    raw = _load_yaml(path)
    if normalized_type == "jobs_config":
        # The legacy file may still contain platform acquisition fields.  Only
        # the explicit user whitelist becomes a user-editable default.
        raw = {key: value for key, value in raw.items() if key in _USER_JOBS_KEYS}
    model = _validate_model(_CONFIG_MODELS[normalized_type], raw, path)
    return _model_dump(model)


def merge_config(
    default: Mapping[str, Any], override: Mapping[str, Any]
) -> dict[str, Any]:
    """Recursively merge JSON mappings without mutating either input."""

    if not isinstance(default, Mapping) or not isinstance(override, Mapping):
        raise ConfigLoadError("Configuration defaults and overrides must be mappings")
    result: dict[str, Any] = deepcopy(dict(default))
    for key, value in override.items():
        if not isinstance(key, str) or key.startswith("__"):
            raise ConfigLoadError("Configuration keys must be safe strings")
        existing = result.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            result[key] = merge_config(existing, value)
        else:
            result[key] = deepcopy(value)
    if _depth(result) > MAX_CONFIG_DEPTH:
        raise ConfigLoadError(f"Configuration nesting exceeds {MAX_CONFIG_DEPTH} levels")
    return result


def validate_user_config(config_type: str, data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one effective user document."""

    normalized_type = _require_config_type(config_type)
    if not isinstance(data, Mapping):
        raise ConfigLoadError("Configuration data must be a mapping")
    model = _validate_model(_CONFIG_MODELS[normalized_type], data, normalized_type)
    return _model_dump(model)


def effective_config_hash(effective: Mapping[str, Any]) -> str:
    """Return a deterministic SHA-256 hash for normalized effective config."""

    payload = json.dumps(
        deepcopy(dict(effective)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _override_and_revision(value: Mapping[str, Any] | None) -> tuple[dict[str, Any], int]:
    if value is None:
        return {}, 0
    raw = deepcopy(dict(value))
    if "override_json" in raw or "revision" in raw:
        override = raw.get("override_json") or {}
        if not isinstance(override, Mapping):
            raise ConfigLoadError("override_json must be a mapping")
        try:
            revision = int(raw.get("revision") or 0)
        except (TypeError, ValueError) as exc:
            raise ConfigLoadError("revision must be an integer") from exc
        if revision < 0:
            raise ConfigLoadError("revision cannot be negative")
        return deepcopy(dict(override)), revision
    return raw, 0


def build_config_snapshot(
    overrides_by_type: Mapping[str, Mapping[str, Any] | None],
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """Build a detached, validated immutable-by-convention config snapshot."""

    unsupported = set(overrides_by_type) - set(CONFIG_TYPES)
    if unsupported:
        raise ConfigLoadError(f"Unsupported config override types: {sorted(unsupported)}")

    configs: dict[str, dict[str, Any]] = {}
    revisions: dict[str, int] = {}
    for config_type in CONFIG_TYPES:
        default = load_default_config(config_type, project_root)
        override, revision = _override_and_revision(overrides_by_type.get(config_type))
        effective = merge_config(default, override)
        configs[config_type] = validate_user_config(config_type, effective)
        revisions[config_type] = revision

    snapshot_body = {
        "schema_version": 1,
        "configs": configs,
        "config_revision_map": revisions,
    }
    return deepcopy(
        {
            **snapshot_body,
            "config_hash": effective_config_hash(snapshot_body),
        }
    )


def load_platform_connector_config(
    project_root: str | Path | None = None,
) -> PlatformConnectorConfig:
    path = _root(project_root) / "config" / "platform_connector_config.yml"
    return _validate_model(PlatformConnectorConfig, _load_yaml(path), path)


def load_effective_user_config(
    overrides_by_type: Mapping[str, Mapping[str, Any] | None] | None = None,
    project_root: str | Path | None = None,
) -> EffectiveUserConfig:
    snapshot = build_config_snapshot(overrides_by_type or {}, project_root)
    return EffectiveUserConfig.model_validate(snapshot["configs"])


def load_configs(project_root: str | Path = ".") -> ConfigBundle:
    """Load platform config and repository user defaults with legacy accessors."""

    platform = load_platform_connector_config(project_root)
    effective = load_effective_user_config({}, project_root)
    legacy_jobs = LegacyJobsConfig(
        global_filters=platform.global_filters,
        freshness_filter=platform.freshness_filter,
        job_categories=list(effective.jobs_config.job_categories),
        ranking_weights=effective.jobs_config.ranking_weights,
        output=effective.jobs_config.output,
    )
    return ConfigBundle(
        platform_connector=platform,
        user_jobs=effective.jobs_config,
        jobs=legacy_jobs,
        candidate_profile=effective.candidate_profile,
        skill_taxonomy=effective.skill_taxonomy,
    )
