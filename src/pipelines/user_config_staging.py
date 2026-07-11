"""Stage immutable user configuration snapshots for dbt.

This module intentionally has no imports from ``src.connectors``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping
from uuid import UUID

from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.loader import CONFIG_TYPES, effective_config_hash, validate_user_config


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a valid UUID") from exc


def validate_config_snapshot(config_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a detached worker snapshot and verify its deterministic hash."""

    snapshot = deepcopy(dict(config_snapshot))
    configs = snapshot.get("configs")
    if not isinstance(configs, Mapping):
        raise ValueError("config_snapshot.configs must be a mapping")
    if set(configs) != set(CONFIG_TYPES):
        raise ValueError(f"config_snapshot.configs must contain exactly {CONFIG_TYPES}")
    normalized_configs = {
        config_type: validate_user_config(config_type, configs[config_type])
        for config_type in CONFIG_TYPES
    }
    revisions = snapshot.get("config_revision_map") or {}
    if not isinstance(revisions, Mapping):
        raise ValueError("config_revision_map must be a mapping")
    normalized_revisions = {
        config_type: int(revisions.get(config_type) or 0) for config_type in CONFIG_TYPES
    }
    body = {
        "schema_version": int(snapshot.get("schema_version") or 1),
        "configs": normalized_configs,
        "config_revision_map": normalized_revisions,
    }
    calculated_hash = effective_config_hash(body)
    supplied_hash = str(snapshot.get("config_hash") or "")
    if supplied_hash and supplied_hash != calculated_hash:
        raise ValueError("config snapshot hash does not match its effective configuration")
    return {**body, "config_hash": calculated_hash}


def stage_user_config_snapshot(
    user_uuid: str,
    run_uuid: str,
    config_snapshot: Mapping[str, Any],
    *,
    service: MotherDuckService | None = None,
) -> dict[str, Any]:
    """Write only the supplied user's exact run partition into bridge tables."""

    user = _uuid(user_uuid, "user_uuid")
    run = _uuid(run_uuid, "run_uuid")
    snapshot = validate_config_snapshot(config_snapshot)
    md = service or MotherDuckService()
    init_motherduck_schema(md)
    counts = MotherDuckIngestionWriter(md).write_user_config_snapshot(user, run, snapshot)
    return {
        "user_uuid": user,
        "run_uuid": run,
        "config_hash": snapshot["config_hash"],
        "staged_rows": counts,
        "snapshot": snapshot,
    }
