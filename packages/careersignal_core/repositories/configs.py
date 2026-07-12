"""Versioned per-user configuration overrides and immutable snapshots."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Mapping
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.repositories.errors import NotFoundError
from packages.careersignal_core.storage.postgres import PostgresStore
from src.config.loader import (
    CONFIG_TYPES,
    build_config_snapshot,
    effective_config_hash,
    load_default_config,
    merge_config,
    validate_user_config,
)


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _field_sources(default: Any, override: Any, prefix: str = "") -> dict[str, str]:
    sources: dict[str, str] = {}
    if isinstance(default, Mapping):
        override_map = override if isinstance(override, Mapping) else {}
        for key, value in default.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                sources.update(_field_sources(value, override_map.get(key), path))
            else:
                sources[path] = "override" if key in override_map else "default"
        for key in override_map.keys() - default.keys():
            path = f"{prefix}.{key}" if prefix else str(key)
            sources[path] = "override"
    return sources


def _remove_field(document: dict[str, Any], field_path: str) -> dict[str, Any]:
    parts = [part for part in field_path.split(".") if part]
    if not parts:
        raise ValueError("A field path is required")
    result = deepcopy(document)
    cursor: dict[str, Any] = result
    parents: list[tuple[dict[str, Any], str]] = []
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            return result
        parents.append((cursor, part))
        cursor = child
    cursor.pop(parts[-1], None)
    for parent, key in reversed(parents):
        value = parent.get(key)
        if isinstance(value, dict) and not value:
            parent.pop(key, None)
    return result


class ConfigRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def _require_type(self, config_type: str) -> str:
        if config_type not in CONFIG_TYPES:
            raise NotFoundError("Configuration type was not found")
        return config_type

    def _row(self, user_uuid: UUID | str, config_type: str) -> dict[str, Any]:
        config_type = self._require_type(config_type)
        row = self.store.fetch_one(
            """
            select config_uuid, user_uuid, config_type::text as config_type, override_json,
                   schema_version, revision, effective_config_hash, created_at, updated_at
            from public.user_config_documents
            where user_uuid = %s and config_type = %s::public.config_type
            """,
            [str(user_uuid), config_type],
        )
        if row is None:
            raise NotFoundError("Configuration was not found")
        return row

    def get(self, user_uuid: UUID | str, config_type: str) -> dict[str, Any]:
        row = self._row(user_uuid, config_type)
        default = load_default_config(config_type)
        override = _dict(row.get("override_json"))
        effective = validate_user_config(config_type, merge_config(default, override))
        return {
            **row,
            "default_config": default,
            "override_config": override,
            "effective_config": effective,
            "field_sources": _field_sources(default, override),
            "effective_config_hash": effective_config_hash(effective),
        }

    def list(self, user_uuid: UUID | str) -> list[dict[str, Any]]:
        return [self.get(user_uuid, config_type) for config_type in CONFIG_TYPES]

    def _save(
        self,
        *,
        user_uuid: UUID | str,
        config_type: str,
        override: Mapping[str, Any],
        changed_by_user_uuid: UUID | str,
        change_source: str,
    ) -> dict[str, Any]:
        config_type = self._require_type(config_type)
        default = load_default_config(config_type)
        normalized_override = deepcopy(dict(override))
        effective = validate_user_config(config_type, merge_config(default, normalized_override))
        digest = effective_config_hash(effective)

        with self.store.transaction() as connection:
            current = connection.execute(
                """
                select revision from public.user_config_documents
                where user_uuid = %s and config_type = %s::public.config_type
                for update
                """,
                [str(user_uuid), config_type],
            ).fetchone()
            if current is None:
                raise NotFoundError("Configuration was not found")
            revision = int(current["revision"]) + 1
            connection.execute(
                """
                insert into public.user_config_versions (
                    user_uuid, config_type, revision, override_json,
                    changed_by_user_uuid, change_source
                ) values (%s, %s::public.config_type, %s, %s::jsonb, %s, %s)
                """,
                [
                    str(user_uuid),
                    config_type,
                    revision,
                    Jsonb(normalized_override),
                    str(changed_by_user_uuid),
                    change_source,
                ],
            )
            connection.execute(
                """
                update public.user_config_documents
                set override_json = %s::jsonb, revision = %s,
                    effective_config_hash = %s, updated_at = now()
                where user_uuid = %s and config_type = %s::public.config_type
                """,
                [Jsonb(normalized_override), revision, digest, str(user_uuid), config_type],
            )
            connection.execute(
                """
                insert into public.user_activity_events (user_uuid, event_name, metadata)
                values (%s, 'config_updated', jsonb_build_object(
                    'config_type', %s::text,
                    'revision', %s::integer,
                    'change_source', %s::text
                ))
                """,
                [str(user_uuid), config_type, revision, change_source],
            )
        return self.get(user_uuid, config_type)

    def update(
        self,
        *,
        user_uuid: UUID | str,
        config_type: str,
        override_config: Mapping[str, Any],
        changed_by_user_uuid: UUID | str,
    ) -> dict[str, Any]:
        return self._save(
            user_uuid=user_uuid,
            config_type=config_type,
            override=override_config,
            changed_by_user_uuid=changed_by_user_uuid,
            change_source="user_update",
        )

    def reset(
        self, *, user_uuid: UUID | str, config_type: str, changed_by_user_uuid: UUID | str
    ) -> dict[str, Any]:
        return self._save(
            user_uuid=user_uuid,
            config_type=config_type,
            override={},
            changed_by_user_uuid=changed_by_user_uuid,
            change_source="reset_document",
        )

    def reset_field(
        self,
        *,
        user_uuid: UUID | str,
        config_type: str,
        field_path: str,
        changed_by_user_uuid: UUID | str,
    ) -> dict[str, Any]:
        current = self._row(user_uuid, config_type)
        return self._save(
            user_uuid=user_uuid,
            config_type=config_type,
            override=_remove_field(_dict(current.get("override_json")), field_path),
            changed_by_user_uuid=changed_by_user_uuid,
            change_source="reset_field",
        )

    def versions(self, user_uuid: UUID | str, config_type: str) -> list[dict[str, Any]]:
        self._require_type(config_type)
        return self.store.fetch_all(
            """
            select version_uuid, user_uuid, config_type::text as config_type, revision,
                   override_json, changed_by_user_uuid, change_source, created_at
            from public.user_config_versions
            where user_uuid = %s and config_type = %s::public.config_type
            order by revision desc
            """,
            [str(user_uuid), config_type],
        )

    def restore(
        self,
        *,
        user_uuid: UUID | str,
        config_type: str,
        revision: int,
        changed_by_user_uuid: UUID | str,
    ) -> dict[str, Any]:
        self._require_type(config_type)
        historic = self.store.fetch_one(
            """
            select override_json from public.user_config_versions
            where user_uuid = %s and config_type = %s::public.config_type and revision = %s
            """,
            [str(user_uuid), config_type, revision],
        )
        if historic is None:
            raise NotFoundError("Configuration revision was not found")
        return self._save(
            user_uuid=user_uuid,
            config_type=config_type,
            override=_dict(historic.get("override_json")),
            changed_by_user_uuid=changed_by_user_uuid,
            change_source=f"restore_revision:{revision}",
        )

    def snapshot(self, user_uuid: UUID | str) -> dict[str, Any]:
        rows = {
            row["config_type"]: {
                "override_json": _dict(row.get("override_json")),
                "revision": int(row.get("revision") or 1),
            }
            for row in self.store.fetch_all(
                """
                select config_type::text as config_type, override_json, revision
                from public.user_config_documents
                where user_uuid = %s
                """,
                [str(user_uuid)],
            )
        }
        if set(rows) != set(CONFIG_TYPES):
            raise NotFoundError("One or more user configuration documents are missing")
        return build_config_snapshot(rows)

    def active_user_snapshots(self) -> list[dict[str, Any]]:
        """Return effective config snapshots for every active non-Demo user."""

        rows = self.store.fetch_all(
            """
            select p.user_uuid, d.config_type::text as config_type, d.override_json, d.revision
            from public.user_profiles p
            join public.user_config_documents d on d.user_uuid = p.user_uuid
            where p.deleted_at is null
              and p.account_status = 'active'
              and p.role = 'user'
              and p.expires_at > now()
            order by p.created_at, p.user_uuid, d.config_type
            """
        )
        grouped: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            user_uuid = str(row["user_uuid"])
            grouped.setdefault(user_uuid, {})[row["config_type"]] = {
                "override_json": _dict(row.get("override_json")),
                "revision": int(row.get("revision") or 1),
            }

        snapshots: list[dict[str, Any]] = []
        for user_uuid, documents in grouped.items():
            if set(documents) != set(CONFIG_TYPES):
                raise NotFoundError(f"Configuration documents are missing for user {user_uuid}")
            snapshots.append({"user_uuid": user_uuid, **build_config_snapshot(documents)})
        return snapshots

    def is_eligible_for_global_refresh(self, user_uuid: UUID | str) -> bool:
        row = self.store.fetch_one(
            """
            select 1
            from public.user_profiles
            where user_uuid = %s
              and deleted_at is null
              and account_status = 'active'
              and role = 'user'
              and expires_at > now()
            limit 1
            """,
            [str(user_uuid)],
        )
        return row is not None
