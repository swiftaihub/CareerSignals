"""Structural persistence contract used by the preferences service."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID


class PreferencesRepositoryProtocol(Protocol):
    def load_current(self, user_uuid: UUID | str) -> dict[str, Any]: ...

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
        validation_warnings: Sequence[str] = (),
    ) -> dict[str, Any]: ...

    def list_bundle_revisions(
        self, user_uuid: UUID | str, *, limit: int, offset: int
    ) -> list[dict[str, Any]]: ...

    def restore_bundle(
        self,
        *,
        user_uuid: UUID | str,
        bundle_revision_uuid: UUID | str,
        changed_by_user_uuid: UUID | str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]: ...

    def reset_bundle(
        self,
        *,
        user_uuid: UUID | str,
        changed_by_user_uuid: UUID | str,
        expected_revision: int | None = None,
    ) -> dict[str, Any]: ...

    def search_shared_options(
        self, kind: str, query: str = "", *, limit: int, offset: int
    ) -> dict[str, Any] | list[str]: ...

    def lookup_skill_aliases(self, normalized_canonicals: Sequence[str]) -> Mapping[str, Any]: ...

    def upsert_skill_aliases(self, records: Sequence[Mapping[str, Any]]) -> None: ...
