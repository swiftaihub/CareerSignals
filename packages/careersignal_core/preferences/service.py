"""Application service coordinating preference reads, previews, and bundle writes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable
from uuid import UUID

from packages.careersignal_core.preferences.compiler import PreferencesCompiler
from packages.careersignal_core.preferences.completeness import profile_completeness
from packages.careersignal_core.preferences.models import (
    PreferencesDocument,
    PreferencesPayload,
)
from packages.careersignal_core.preferences.normalization import (
    normalized_key,
    sanitize_text,
)
from packages.careersignal_core.preferences.options import fixed_options
from packages.careersignal_core.preferences.repository import PreferencesRepositoryProtocol
from packages.careersignal_core.preferences.reverse_mapping import (
    effective_configs_from_state,
    history_items,
    payload_from_state,
    revision_metadata,
)
from packages.careersignal_core.repositories.errors import ConfigBundleConflictError, NotFoundError


SOURCE_UI_VERSION = "settings-v1"
DYNAMIC_OPTION_KINDS = frozenset({"locations", "industries", "companies", "job_titles"})


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _legacy_alias_catalog(configs: Mapping[str, Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    taxonomy = _mapping(_mapping(configs.get("skill_taxonomy")).get("skill_aliases"))
    output: dict[str, list[dict[str, Any]]] = {}
    for raw in taxonomy.values():
        value = _mapping(raw)
        canonical = sanitize_text(value.get("canonical"))
        if not canonical:
            continue
        key = normalized_key(canonical)
        for alias in [canonical, *(value.get("aliases") or [])]:
            clean_alias = sanitize_text(alias)
            if clean_alias:
                output.setdefault(key, []).append(
                    {"alias": clean_alias, "confidence": 1.0, "source": "current_config"}
                )
    return output


def _merge_catalogs(*catalogs: Mapping[str, Any]) -> dict[str, list[Any]]:
    output: dict[str, list[Any]] = {}
    for catalog in catalogs:
        for key, value in catalog.items():
            values = value if isinstance(value, list) else [value]
            output.setdefault(normalized_key(key), []).extend(values)
    return output


def _catalog_rows(compiled: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in compiled.get("catalog_entries") or []:
        value = _mapping(record)
        canonical = sanitize_text(value.get("canonical_skill"))
        normalized_canonical = normalized_key(canonical)
        for alias in value.get("aliases") or []:
            clean_alias = sanitize_text(alias)
            normalized_alias = normalized_key(clean_alias)
            key = (normalized_canonical, normalized_alias)
            if not canonical or not clean_alias or key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "canonical_skill": canonical,
                    "normalized_canonical_skill": normalized_canonical,
                    "alias": clean_alias,
                    "normalized_alias": normalized_alias,
                    "category": value.get("category"),
                    "industry": value.get("industry"),
                    "source": value.get("source") or "deterministic",
                    "confidence": value.get("confidence", 1.0),
                    "generator_version": value.get("generator_version") or "skill-alias-rules-v1",
                }
            )
    return rows


class PreferencesService:
    def __init__(
        self,
        repository: PreferencesRepositoryProtocol,
        *,
        compiler: PreferencesCompiler | None = None,
    ) -> None:
        self.repository = repository
        self.compiler = compiler or PreferencesCompiler()

    def _history(
        self,
        user_uuid: UUID | str,
        *,
        current_bundle_uuid: UUID | str | None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Any]:
        records = self.repository.list_bundle_revisions(user_uuid, limit=limit, offset=offset)
        current = str(current_bundle_uuid) if current_bundle_uuid else None
        marked = [
            {
                **dict(record),
                "is_current": bool(
                    current
                    and str(
                        record.get("bundle_revision_uuid") or record.get("bundle_uuid") or ""
                    )
                    == current
                ),
            }
            for record in records
        ]
        return history_items(marked)

    def _document(
        self,
        user_uuid: UUID | str,
        state: Mapping[str, Any],
        *,
        include_history: bool,
        completeness_confirmed: bool | None = None,
    ) -> PreferencesDocument:
        preferences, preview, warnings, confirmed = payload_from_state(state)
        if completeness_confirmed is not None:
            confirmed = completeness_confirmed
        revision = revision_metadata(state)
        history = (
            self._history(user_uuid, current_bundle_uuid=revision.bundle_uuid)
            if include_history
            else []
        )
        return PreferencesDocument(
            **preferences.model_dump(),
            generated_preview=preview,
            revision=revision,
            revision_history=history,
            profile_completeness=profile_completeness(preferences, confirmed=confirmed),
            warnings=list(dict.fromkeys(warnings)),
            is_confirmed=confirmed,
        )

    def get_preferences(self, user_uuid: UUID | str) -> PreferencesDocument:
        state = self.repository.load_current(user_uuid)
        return self._document(user_uuid, state, include_history=True)

    def _compile(
        self,
        user_uuid: UUID | str,
        preferences: PreferencesPayload,
        *,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        configs = effective_configs_from_state(state)
        keys = [normalized_key(skill.name) for skill in preferences.skills]
        shared_catalog = self.repository.lookup_skill_aliases(keys)
        alias_catalog = _merge_catalogs(_legacy_alias_catalog(configs), shared_catalog)
        return self.compiler.compile(
            preferences,
            base_configs=configs,
            alias_catalog=alias_catalog,
        )

    def preview(
        self,
        user_uuid: UUID | str,
        preferences: PreferencesPayload,
    ) -> PreferencesDocument:
        state = self.repository.load_current(user_uuid)
        compiled = self._compile(user_uuid, preferences, state=state)
        revision = revision_metadata(state)
        return PreferencesDocument(
            **preferences.model_dump(),
            generated_preview=compiled["generated_preview"],
            revision=revision,
            revision_history=[],
            profile_completeness=profile_completeness(preferences, confirmed=True),
            warnings=compiled["warnings"],
            is_confirmed=False,
        )

    @staticmethod
    def _expected_revision(
        state: Mapping[str, Any],
        *,
        expected_bundle_revision_uuid: UUID | str | None,
        expected_revision: int | None,
    ) -> int:
        current_uuid = state.get("bundle_revision_uuid")
        if expected_bundle_revision_uuid is not None and str(expected_bundle_revision_uuid) != str(current_uuid):
            raise ConfigBundleConflictError(
                "Preferences changed since they were loaded; reload before saving"
            )
        current_revision = int(state.get("revision") or 0)
        if expected_revision is not None and int(expected_revision) != current_revision:
            raise ConfigBundleConflictError(
                "Preferences changed since they were loaded; reload before saving"
            )
        return current_revision

    def save_preferences(
        self,
        user_uuid: UUID | str,
        preferences: PreferencesPayload,
        *,
        changed_by_user_uuid: UUID | str,
        expected_bundle_revision_uuid: UUID | str | None = None,
        expected_revision: int | None = None,
        source_ui_version: str = SOURCE_UI_VERSION,
    ) -> PreferencesDocument:
        state = self.repository.load_current(user_uuid)
        repository_revision = self._expected_revision(
            state,
            expected_bundle_revision_uuid=expected_bundle_revision_uuid,
            expected_revision=expected_revision,
        )
        compiled = self._compile(user_uuid, preferences, state=state)
        self.repository.upsert_skill_aliases(_catalog_rows(compiled))
        saved = self.repository.save_bundle(
            user_uuid,
            compiled_overrides=compiled["compiled_overrides"],
            preferences_json=preferences.model_dump(mode="json"),
            generated_preview=compiled["generated_preview"].model_dump(mode="json"),
            generator_version=compiled["generator_version"],
            source_ui_version=sanitize_text(source_ui_version)[:160] or SOURCE_UI_VERSION,
            expected_revision=repository_revision,
            changed_by_user_uuid=changed_by_user_uuid,
            validation_warnings=compiled["warnings"],
        )
        return self._document(user_uuid, saved, include_history=True, completeness_confirmed=True)

    def list_history(
        self,
        user_uuid: UUID | str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Any]:
        state = self.repository.load_current(user_uuid)
        return self._history(
            user_uuid,
            current_bundle_uuid=state.get("bundle_revision_uuid"),
            limit=limit,
            offset=offset,
        )

    def restore(
        self,
        user_uuid: UUID | str,
        bundle_uuid: UUID | str,
        *,
        changed_by_user_uuid: UUID | str,
        expected_bundle_revision_uuid: UUID | str | None = None,
        expected_revision: int | None = None,
    ) -> PreferencesDocument:
        state = self.repository.load_current(user_uuid)
        repository_revision = self._expected_revision(
            state,
            expected_bundle_revision_uuid=expected_bundle_revision_uuid,
            expected_revision=expected_revision,
        )
        self.repository.restore_bundle(
            user_uuid=user_uuid,
            bundle_revision_uuid=bundle_uuid,
            changed_by_user_uuid=changed_by_user_uuid,
            expected_revision=repository_revision,
        )
        return self.get_preferences(user_uuid)

    def reset(
        self,
        user_uuid: UUID | str,
        *,
        changed_by_user_uuid: UUID | str,
        expected_bundle_revision_uuid: UUID | str | None = None,
        expected_revision: int | None = None,
    ) -> PreferencesDocument:
        state = self.repository.load_current(user_uuid)
        repository_revision = self._expected_revision(
            state,
            expected_bundle_revision_uuid=expected_bundle_revision_uuid,
            expected_revision=expected_revision,
        )
        self.repository.reset_bundle(
            user_uuid=user_uuid,
            changed_by_user_uuid=changed_by_user_uuid,
            expected_revision=repository_revision,
        )
        return self.get_preferences(user_uuid)

    def restore_identifier(
        self,
        user_uuid: UUID | str,
        identifier: str,
        *,
        changed_by_user_uuid: UUID | str,
    ) -> PreferencesDocument:
        try:
            bundle_uuid = UUID(str(identifier))
        except (TypeError, ValueError, AttributeError):
            try:
                requested_revision = int(identifier)
            except (TypeError, ValueError) as exc:
                raise NotFoundError("Configuration bundle revision was not found") from exc
            record = next(
                (
                    item
                    for item in self.repository.list_bundle_revisions(user_uuid, limit=100, offset=0)
                    if int(item.get("revision") or 0) == requested_revision
                ),
                None,
            )
            if record is None:
                raise NotFoundError("Configuration bundle revision was not found")
            bundle_uuid = UUID(
                str(record.get("bundle_revision_uuid") or record.get("bundle_uuid"))
            )
        return self.restore(
            user_uuid,
            bundle_uuid,
            changed_by_user_uuid=changed_by_user_uuid,
        )

    def options(
        self,
        *,
        kind: str | None,
        query: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            **fixed_options(),
            "locations": [],
            "industries": [],
            "companies": [],
            "job_titles": [],
            "pagination": None,
        }
        if kind is None:
            for dynamic_kind in sorted(DYNAMIC_OPTION_KINDS):
                page = self.repository.search_shared_options(
                    dynamic_kind,
                    sanitize_text(query)[:160],
                    limit=limit,
                    offset=offset,
                )
                raw_items = page.get("items") or [] if isinstance(page, Mapping) else page
                seen: set[str] = set()
                for raw in raw_items:
                    value = sanitize_text(
                        _mapping(raw).get("value") if isinstance(raw, Mapping) else raw
                    )
                    if value and value.casefold() not in seen:
                        seen.add(value.casefold())
                        result[dynamic_kind].append({"value": value, "label": value})
            return result
        normalized_kind = sanitize_text(kind).casefold()
        if normalized_kind not in DYNAMIC_OPTION_KINDS:
            raise ValueError(f"Unsupported dynamic option kind: {kind}")
        page = self.repository.search_shared_options(
            normalized_kind,
            sanitize_text(query)[:160],
            limit=limit,
            offset=offset,
        )
        if isinstance(page, Mapping):
            raw_items: Iterable[Any] = page.get("items") or []
            total = int(page.get("total") or 0)
            page_limit = int(page.get("limit") or limit)
            page_offset = int(page.get("offset") or offset)
        else:
            raw_items = page
            total = len(page)
            page_limit = limit
            page_offset = offset
        items: list[dict[str, str]] = []
        seen: set[str] = set()
        for raw in raw_items:
            value = sanitize_text(_mapping(raw).get("value") if isinstance(raw, Mapping) else raw)
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                items.append({"value": value, "label": value})
        result[normalized_kind] = items
        result["pagination"] = {
            "kind": normalized_kind,
            "query": sanitize_text(query)[:160],
            "limit": page_limit,
            "offset": page_offset,
            "total": total,
            "has_more": page_offset + len(items) < total,
        }
        return result
