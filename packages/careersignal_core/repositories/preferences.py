"""Atomic persistence for user-friendly preferences and compiled config bundles."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from packages.careersignal_core.repositories.configs import _coherent_bundle_uuid
from packages.careersignal_core.repositories.errors import (
    ConfigBundleConflictError,
    NotFoundError,
)
from packages.careersignal_core.storage.postgres import PostgresStore
from src.config.loader import (
    CONFIG_TYPES,
    build_config_snapshot,
    effective_config_hash,
    load_default_config,
    merge_config,
    validate_user_config,
)


BUNDLE_COLUMNS = """
bundle_revision_uuid, user_uuid, revision,
preferences_json as preferences, generated_preview_json as generated_preview,
validation_warnings, compiled_overrides, compiled_configs,
config_revision_map, config_hash, generator_version, source_ui_version,
status, created_by_user_uuid, restored_from_bundle_revision_uuid, created_at
"""

OPTION_COLUMNS: dict[str, str] = {
    "companies": "company_name",
    "company": "company_name",
    "job_titles": "title",
    "titles": "title",
    "locations": "location",
    "industries": "industry",
    "seniority": "seniority",
    "work_arrangements": "work_arrangement",
}


def _uuid(value: UUID | str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{field} must be a valid UUID") from exc


def _json_value(value: Any, field: str) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be JSON serializable") from exc


def _json_object(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    normalized = _json_value(dict(value), field)
    if not isinstance(normalized, dict):  # defensive after JSON normalization
        raise ValueError(f"{field} must be a mapping")
    return normalized


def _warning_list(value: Sequence[str] | None) -> list[str]:
    warnings: list[str] = []
    for item in value or ():
        warning = str(item).strip()
        if warning and warning not in warnings:
            warnings.append(warning[:1000])
    return warnings[:100]


def _compiled_bundle(
    compiled_overrides: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if set(compiled_overrides) != set(CONFIG_TYPES):
        raise ValueError(f"compiled_overrides must contain exactly {CONFIG_TYPES}")

    overrides: dict[str, dict[str, Any]] = {}
    configs: dict[str, dict[str, Any]] = {}
    for config_type in CONFIG_TYPES:
        raw_override = compiled_overrides[config_type]
        if not isinstance(raw_override, Mapping):
            raise ValueError(f"compiled_overrides.{config_type} must be a mapping")
        override = _json_object(raw_override, f"compiled_overrides.{config_type}")
        effective = validate_user_config(
            config_type,
            merge_config(load_default_config(config_type), override),
        )
        overrides[config_type] = override
        configs[config_type] = effective
    return overrides, configs


class PreferencesRepository:
    """Persist one logical Settings revision and all three generated configs."""

    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def load_current(self, user_uuid: UUID | str) -> dict[str, Any]:
        user_key = _uuid(user_uuid, "user_uuid")
        rows = self.store.fetch_all(
            """
            select config_uuid, user_uuid, config_type::text as config_type,
                   override_json, schema_version, revision, effective_config_hash,
                   bundle_revision_uuid, created_at, updated_at
            from public.user_config_documents
            where user_uuid = %s
            order by config_type
            """,
            [user_key],
        )
        documents = {str(row["config_type"]): dict(row) for row in rows}
        if set(documents) != set(CONFIG_TYPES):
            raise NotFoundError("One or more user configuration documents are missing")

        effective_configs: dict[str, dict[str, Any]] = {}
        overrides: dict[str, dict[str, Any]] = {}
        for config_type, row in documents.items():
            raw_override = row.get("override_json")
            override = dict(raw_override) if isinstance(raw_override, Mapping) else {}
            effective_configs[config_type] = validate_user_config(
                config_type,
                merge_config(load_default_config(config_type), override),
            )
            overrides[config_type] = deepcopy(override)

        bundle_uuid = _coherent_bundle_uuid(documents)
        bundle = self.get_bundle(user_key, bundle_uuid) if bundle_uuid else None
        revision = int(bundle.get("revision") or 0) if bundle else 0
        return {
            "user_uuid": user_key,
            "revision": revision,
            "bundle_revision_uuid": bundle_uuid,
            "bundle": bundle,
            "preferences": deepcopy(bundle.get("preferences") or {}) if bundle else {},
            "generated_preview": (
                deepcopy(bundle.get("generated_preview") or {}) if bundle else {}
            ),
            "validation_warnings": (
                list(bundle.get("validation_warnings") or [])
                if bundle
                else ["Legacy configuration has no coherent preference bundle."]
            ),
            "compiled_overrides": overrides,
            "compiled_configs": effective_configs,
            # Compatibility aliases consumed by the reverse-mapping service.
            "override_configs": overrides,
            "effective_configs": effective_configs,
            "configs": effective_configs,
            "config_documents": documents,
            "documents": [
                {
                    **documents[config_type],
                    "override_config": overrides[config_type],
                    "effective_config": effective_configs[config_type],
                }
                for config_type in CONFIG_TYPES
            ],
        }

    def save_bundle(
        self,
        user_uuid: UUID | str,
        *,
        compiled_overrides: Mapping[str, Mapping[str, Any]],
        preferences_json: Mapping[str, Any],
        generated_preview: Mapping[str, Any],
        generator_version: str,
        source_ui_version: str,
        expected_revision: int | None,
        changed_by_user_uuid: UUID | str,
        validation_warnings: Sequence[str] | None = None,
        _status: str = "saved",
        _restored_from_bundle_revision_uuid: UUID | str | None = None,
        _change_source: str = "preferences_bundle_save",
    ) -> dict[str, Any]:
        user_key = _uuid(user_uuid, "user_uuid")
        actor_key = _uuid(changed_by_user_uuid, "changed_by_user_uuid")
        preferences = _json_object(preferences_json, "preferences_json")
        preview = _json_object(generated_preview, "generated_preview")
        warnings = _warning_list(validation_warnings)
        overrides, configs = _compiled_bundle(compiled_overrides)
        generator = str(generator_version).strip()
        ui_version = str(source_ui_version).strip()
        if not generator or len(generator) > 160:
            raise ValueError("generator_version must contain 1 to 160 characters")
        if not ui_version or len(ui_version) > 160:
            raise ValueError("source_ui_version must contain 1 to 160 characters")
        if expected_revision is not None and int(expected_revision) < 0:
            raise ValueError("expected_revision cannot be negative")
        restored_from = (
            _uuid(_restored_from_bundle_revision_uuid, "restored_from_bundle_revision_uuid")
            if _restored_from_bundle_revision_uuid is not None
            else None
        )
        bundle_uuid = str(uuid4())

        with self.store.transaction() as connection:
            connection.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"careersignals:config-bundle:{user_key}"],
            )
            current_rows = connection.execute(
                """
                select config_type::text as config_type, revision, bundle_revision_uuid
                from public.user_config_documents
                where user_uuid = %s
                order by config_type
                for update
                """,
                [user_key],
            ).fetchall()
            current_documents = {
                str(row["config_type"]): dict(row) for row in current_rows
            }
            if set(current_documents) != set(CONFIG_TYPES):
                raise NotFoundError("One or more user configuration documents are missing")

            current_bundle_uuid = _coherent_bundle_uuid(current_documents)
            current_revision = 0
            if current_bundle_uuid:
                current_bundle = connection.execute(
                    """
                    select revision
                    from public.config_bundle_revisions
                    where user_uuid = %s and bundle_revision_uuid = %s
                    """,
                    [user_key, current_bundle_uuid],
                ).fetchone()
                current_revision = int(current_bundle["revision"]) if current_bundle else 0
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise ConfigBundleConflictError(
                    "Preferences changed since they were loaded; reload before saving"
                )

            next_bundle_row = connection.execute(
                """
                select coalesce(max(revision), 0) + 1 as next_revision
                from public.config_bundle_revisions
                where user_uuid = %s
                """,
                [user_key],
            ).fetchone()
            next_bundle_revision = int(next_bundle_row["next_revision"])
            config_revision_map = {
                config_type: int(current_documents[config_type]["revision"]) + 1
                for config_type in CONFIG_TYPES
            }
            snapshot_inputs = {
                config_type: {
                    "override_json": overrides[config_type],
                    "revision": config_revision_map[config_type],
                }
                for config_type in CONFIG_TYPES
            }
            snapshot = build_config_snapshot(
                snapshot_inputs,
                config_bundle_revision_uuid=bundle_uuid,
            )

            inserted = connection.execute(
                f"""
                insert into public.config_bundle_revisions (
                    bundle_revision_uuid, user_uuid, revision, preferences_json,
                    generated_preview_json, validation_warnings, compiled_overrides,
                    compiled_configs, config_revision_map, config_hash,
                    generator_version, source_ui_version, status,
                    created_by_user_uuid, restored_from_bundle_revision_uuid
                ) values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                returning {BUNDLE_COLUMNS}
                """,
                [
                    bundle_uuid,
                    user_key,
                    next_bundle_revision,
                    Jsonb(preferences),
                    Jsonb(preview),
                    Jsonb(warnings),
                    Jsonb(overrides),
                    Jsonb(configs),
                    Jsonb(config_revision_map),
                    snapshot["config_hash"],
                    generator,
                    ui_version,
                    _status,
                    actor_key,
                    restored_from,
                ],
            ).fetchone()
            if inserted is None:
                raise RuntimeError("Configuration bundle insert returned no row")

            connection.execute(
                """
                select set_config('careersignals.changed_by_user_uuid', %s, true),
                       set_config('careersignals.config_change_source', %s, true)
                """,
                [actor_key, _change_source],
            )
            for config_type in CONFIG_TYPES:
                saved = connection.execute(
                    """
                    update public.user_config_documents
                    set override_json = %s,
                        effective_config_hash = %s,
                        bundle_revision_uuid = %s,
                        updated_at = now()
                    where user_uuid = %s and config_type = %s::public.config_type
                    returning revision, bundle_revision_uuid
                    """,
                    [
                        Jsonb(overrides[config_type]),
                        effective_config_hash(configs[config_type]),
                        bundle_uuid,
                        user_key,
                        config_type,
                    ],
                ).fetchone()
                if (
                    saved is None
                    or int(saved["revision"]) != config_revision_map[config_type]
                    or str(saved["bundle_revision_uuid"]) != bundle_uuid
                ):
                    raise RuntimeError(
                        f"Configuration bundle failed to persist {config_type} coherently"
                    )

            version_rows = connection.execute(
                """
                select config_type::text as config_type, revision
                from public.user_config_versions
                where user_uuid = %s and bundle_revision_uuid = %s
                order by config_type
                """,
                [user_key, bundle_uuid],
            ).fetchall()
            persisted_versions = {
                str(row["config_type"]): int(row["revision"]) for row in version_rows
            }
            if persisted_versions != config_revision_map:
                raise RuntimeError("Configuration bundle component history is incomplete")

            connection.execute(
                """
                insert into public.user_activity_events (user_uuid, event_name, metadata)
                values (%s, 'preferences_bundle_saved', jsonb_build_object(
                    'bundle_revision_uuid', %s::text,
                    'bundle_revision', %s::integer,
                    'change_source', %s::text
                ))
                """,
                [user_key, bundle_uuid, next_bundle_revision, _change_source],
            )

        result = dict(inserted)
        result["config_snapshot"] = snapshot
        return result

    def get_bundle(
        self,
        user_uuid: UUID | str,
        bundle_revision_uuid: UUID | str | None,
    ) -> dict[str, Any] | None:
        if bundle_revision_uuid is None:
            return None
        return self.store.fetch_one(
            f"""
            select {BUNDLE_COLUMNS}
            from public.config_bundle_revisions
            where user_uuid = %s and bundle_revision_uuid = %s
            """,
            [
                _uuid(user_uuid, "user_uuid"),
                _uuid(bundle_revision_uuid, "bundle_revision_uuid"),
            ],
        )

    def list_bundle_revisions(
        self,
        user_uuid: UUID | str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit), 100))
        bounded_offset = max(0, int(offset))
        return self.store.fetch_all(
            f"""
            select {BUNDLE_COLUMNS},
                   (
                       select count(*) = 3
                       from public.user_config_documents as documents
                       where documents.user_uuid = bundles.user_uuid
                         and documents.bundle_revision_uuid = bundles.bundle_revision_uuid
                   ) as is_current
            from public.config_bundle_revisions as bundles
            where bundles.user_uuid = %s
            order by bundles.revision desc
            limit %s offset %s
            """,
            [_uuid(user_uuid, "user_uuid"), bounded_limit, bounded_offset],
        )

    def restore_bundle(
        self,
        *,
        user_uuid: UUID | str,
        bundle_revision_uuid: UUID | str,
        changed_by_user_uuid: UUID | str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        user_key = _uuid(user_uuid, "user_uuid")
        source_uuid = _uuid(bundle_revision_uuid, "bundle_revision_uuid")
        source = self.get_bundle(user_key, source_uuid)
        if source is None:
            raise NotFoundError("Configuration bundle revision was not found")

        configs = source.get("compiled_configs")
        warnings = list(source.get("validation_warnings") or [])
        if isinstance(configs, Mapping) and set(configs) == set(CONFIG_TYPES):
            # Full effective configs used as overrides restore the exact generated
            # documents even if repository defaults changed after the old save.
            restore_overrides = {
                config_type: deepcopy(dict(configs[config_type]))
                for config_type in CONFIG_TYPES
            }
        else:
            rows = self.store.fetch_all(
                """
                select config_type::text as config_type, override_json
                from public.user_config_versions
                where user_uuid = %s and bundle_revision_uuid = %s
                order by config_type
                """,
                [user_key, source_uuid],
            )
            restore_overrides = {
                str(row["config_type"]): dict(row.get("override_json") or {})
                for row in rows
            }
            if set(restore_overrides) != set(CONFIG_TYPES):
                raise NotFoundError("Configuration bundle component history is incomplete")
            warnings.append(
                "This legacy revision was restored from sparse overrides using current defaults."
            )

        return self.save_bundle(
            user_key,
            compiled_overrides=restore_overrides,
            preferences_json=dict(source.get("preferences") or {}),
            generated_preview=dict(source.get("generated_preview") or {}),
            validation_warnings=warnings,
            generator_version=str(source.get("generator_version") or "restore-v1"),
            source_ui_version=str(source.get("source_ui_version") or "preferences-v1"),
            expected_revision=expected_revision,
            changed_by_user_uuid=changed_by_user_uuid,
            _status="restored",
            _restored_from_bundle_revision_uuid=source_uuid,
            _change_source=f"restore_bundle:{source_uuid}",
        )

    def reset_bundle(
        self,
        *,
        user_uuid: UUID | str,
        changed_by_user_uuid: UUID | str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        return self.save_bundle(
            user_uuid,
            compiled_overrides={config_type: {} for config_type in CONFIG_TYPES},
            preferences_json={},
            generated_preview={},
            validation_warnings=["Preferences were reset to repository defaults."],
            generator_version="repository-defaults-v1",
            source_ui_version="preferences-v1",
            expected_revision=expected_revision,
            changed_by_user_uuid=changed_by_user_uuid,
            _status="reset",
            _change_source="preferences_bundle_reset",
        )

    def search_shared_options(
        self,
        kind: str,
        query: str = "",
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        normalized_kind = str(kind).strip().casefold()
        column = OPTION_COLUMNS.get(normalized_kind)
        if column is None:
            raise ValueError(f"Unsupported shared option kind: {kind}")
        bounded_limit = max(1, min(int(limit), 100))
        bounded_offset = max(0, int(offset))
        needle = str(query).strip()[:160]
        escaped = needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        rows = self.store.fetch_all(
            f"""
            select {column} as value, count(*)::integer as record_count
            from public.job_postings
            where is_active = true
              and {column} is not null
              and btrim({column}) <> ''
              and {column} ilike %s escape '\\'
            group by {column}
            order by record_count desc, lower({column}), {column}
            limit %s offset %s
            """,
            [pattern, bounded_limit, bounded_offset],
        )
        total = self.store.fetch_one(
            f"""
            select count(distinct {column})::integer as total
            from public.job_postings
            where is_active = true
              and {column} is not null
              and btrim({column}) <> ''
              and {column} ilike %s escape '\\'
            """,
            [pattern],
        )
        return {
            "kind": normalized_kind,
            "query": needle,
            "items": rows,
            "limit": bounded_limit,
            "offset": bounded_offset,
            "total": int((total or {}).get("total") or 0),
        }

    def lookup_skill_aliases(
        self,
        normalized_canonicals: Iterable[str],
    ) -> dict[str, list[dict[str, Any]]]:
        keys = sorted(
            {
                str(value).strip().casefold()
                for value in normalized_canonicals
                if str(value).strip()
            }
        )[:200]
        if not keys:
            return {}
        rows = self.store.fetch_all(
            """
            select skill_alias_uuid, canonical_skill, normalized_canonical_skill,
                   alias, normalized_alias, category, industry, source,
                   confidence, generator_version, created_at, updated_at
            from public.skill_alias_catalog
            where normalized_canonical_skill = any(%s)
            order by normalized_canonical_skill, confidence desc, normalized_alias
            """,
            [keys],
        )
        output = {key: [] for key in keys}
        for row in rows:
            output.setdefault(str(row["normalized_canonical_skill"]), []).append(row)
        return output

    def upsert_skill_aliases(self, records: Iterable[Mapping[str, Any]]) -> None:
        rows: list[list[Any]] = []
        for original in records:
            record = dict(original)
            canonical = str(record.get("canonical_skill") or "").strip()
            normalized_canonical = str(
                record.get("normalized_canonical_skill") or canonical.casefold()
            ).strip()
            source = str(record.get("source") or "deterministic").strip()
            generator = str(record.get("generator_version") or "deterministic-v1").strip()
            confidence = float(record.get("confidence", 1))
            if not 0 <= confidence <= 1:
                raise ValueError("Skill alias confidence must be between 0 and 1")
            raw_aliases = record.get("aliases")
            aliases = (
                list(raw_aliases)
                if isinstance(raw_aliases, (list, tuple, set))
                else [record.get("alias")]
            )
            for raw_alias in aliases:
                alias = str(raw_alias or "").strip()
                supplied_normalized = (
                    record.get("normalized_alias") if len(aliases) == 1 else None
                )
                normalized_alias = str(supplied_normalized or alias.casefold()).strip()
                if not all(
                    (canonical, normalized_canonical, alias, normalized_alias, source, generator)
                ):
                    raise ValueError(
                        "Skill alias records require canonical, alias, source, and version"
                    )
                if max(
                    map(len, (canonical, normalized_canonical, alias, normalized_alias))
                ) > 160:
                    raise ValueError("Skill alias values cannot exceed 160 characters")
                rows.append(
                    [
                        canonical,
                        normalized_canonical,
                        alias,
                        normalized_alias,
                        str(record.get("category") or "").strip() or None,
                        str(record.get("industry") or "").strip() or None,
                        source,
                        confidence,
                        generator,
                    ]
                )
        if not rows:
            return
        with self.store.transaction() as connection:
            connection.executemany(
                """
                insert into public.skill_alias_catalog (
                    canonical_skill, normalized_canonical_skill, alias,
                    normalized_alias, category, industry, source, confidence,
                    generator_version
                ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (normalized_canonical_skill, normalized_alias) do update set
                    canonical_skill = excluded.canonical_skill,
                    alias = excluded.alias,
                    category = coalesce(excluded.category, skill_alias_catalog.category),
                    industry = coalesce(excluded.industry, skill_alias_catalog.industry),
                    source = excluded.source,
                    confidence = excluded.confidence,
                    generator_version = excluded.generator_version,
                    updated_at = now()
                """,
                rows,
            )
