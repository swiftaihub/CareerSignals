from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from apps.api.schemas.common import APIModel
from packages.careersignal_core.preferences.models import (
    MatchPriorities,
    PreferencesDocument,
    PreferencesPayload,
    RevisionHistoryItem,
    SearchPreferences,
    SkillPreference,
)


class PreferencesEditableRequest(APIModel):
    search_preferences: SearchPreferences
    skills: list[SkillPreference] = Field(default_factory=list, max_length=200)
    skill_categories: list[str] = Field(default_factory=list, max_length=30)
    match_priorities: MatchPriorities

    @model_validator(mode="after")
    def require_job_title(self) -> "PreferencesEditableRequest":
        if not self.search_preferences.job_titles:
            raise ValueError("at least one job title is required")
        return self

    def to_payload(self) -> PreferencesPayload:
        return PreferencesPayload(
            search_preferences=self.search_preferences,
            skills=self.skills,
            skill_categories=self.skill_categories,
            match_priorities=self.match_priorities,
        )


class PreferencesUpdateRequest(PreferencesEditableRequest):
    expected_bundle_revision_uuid: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=0)
    source_ui_version: str = Field(default="settings-v1", min_length=1, max_length=160)


class PreferencesMutationRequest(APIModel):
    expected_bundle_revision_uuid: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=0)


class PreferenceOption(APIModel):
    value: str
    label: str


class PreferenceOptionsPagination(APIModel):
    kind: str
    query: str
    limit: int
    offset: int
    total: int
    has_more: bool


class PreferencesOptionsResponse(APIModel):
    countries: list[PreferenceOption] = []
    locations: list[PreferenceOption] = []
    industries: list[PreferenceOption] = []
    seniority_levels: list[PreferenceOption] = []
    employment_types: list[PreferenceOption] = []
    work_arrangements: list[PreferenceOption] = []
    visa_options: list[PreferenceOption] = []
    companies: list[PreferenceOption] = []
    job_titles: list[PreferenceOption] = []
    pagination: PreferenceOptionsPagination | None = None


class PreferencesPreviewResponse(APIModel):
    generated_preview: dict
    derived_candidate_profile: dict
    warnings: list[str]
    profile_completeness: int


PreferenceOptionKind = Literal["locations", "industries", "companies", "job_titles"]

__all__ = [
    "PreferenceOptionKind",
    "PreferencesDocument",
    "PreferencesEditableRequest",
    "PreferencesMutationRequest",
    "PreferencesOptionsResponse",
    "PreferencesPreviewResponse",
    "PreferencesUpdateRequest",
    "RevisionHistoryItem",
]
