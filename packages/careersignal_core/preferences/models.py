"""Typed friendly Preferences DTOs independent of FastAPI."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from packages.careersignal_core.preferences.normalization import (
    dedupe_strings,
    normalize_country_code,
    normalize_employment_type,
    normalize_location_value,
    normalize_visa_preference,
    normalize_work_arrangement,
    sanitize_text,
)


class PreferenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


PreferenceText = Annotated[
    str,
    BeforeValidator(sanitize_text),
    Field(min_length=1, max_length=160),
]
CategoryText = Annotated[
    str,
    BeforeValidator(sanitize_text),
    Field(min_length=1, max_length=80),
]

WorkArrangementCode = Literal["remote", "hybrid", "on_site"]
EmploymentTypeCode = Literal[
    "full_time",
    "part_time",
    "contract",
    "temporary",
    "internship",
    "apprenticeship",
    "freelance",
    "other",
]
VisaPreferenceCode = Literal[
    "sponsorship_required",
    "h1b_transfer_required",
    "sponsorship_preferred",
    "no_sponsorship_required",
    "regardless",
]


class CompensationPreferences(PreferenceModel):
    minimum_salary: float | None = Field(default=None, ge=0, le=100_000_000)
    preferred_salary: float | None = Field(default=None, ge=0, le=100_000_000)
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    period: Literal["annual", "monthly", "hourly"] = "annual"

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str:
        return sanitize_text(value or "USD").upper()

    @model_validator(mode="after")
    def preferred_not_below_minimum(self) -> "CompensationPreferences":
        if (
            self.minimum_salary is not None
            and self.preferred_salary is not None
            and self.preferred_salary < self.minimum_salary
        ):
            raise ValueError("preferred_salary cannot be below minimum_salary")
        return self


class SearchPreferences(PreferenceModel):
    job_titles: list[PreferenceText] = Field(default_factory=list, max_length=25)
    industries: list[PreferenceText] = Field(default_factory=list, max_length=50)
    seniority: list[PreferenceText] = Field(default_factory=list, max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    locations: list[PreferenceText] = Field(default_factory=list, max_length=50)
    work_arrangements: list[WorkArrangementCode] = Field(default_factory=list, max_length=3)
    employment_types: list[EmploymentTypeCode] = Field(default_factory=list, max_length=8)
    visa_preferences: list[VisaPreferenceCode] = Field(default_factory=list, max_length=5)
    excluded_companies: list[PreferenceText] = Field(default_factory=list, max_length=100)
    excluded_titles: list[PreferenceText] = Field(default_factory=list, max_length=100)
    compensation: CompensationPreferences = Field(default_factory=CompensationPreferences)

    @field_validator(
        "job_titles",
        "industries",
        "seniority",
        "excluded_companies",
        "excluded_titles",
        mode="after",
    )
    @classmethod
    def dedupe_text_values(cls, value: list[str]) -> list[str]:
        return dedupe_strings(value)

    @field_validator("locations", mode="before")
    @classmethod
    def normalize_locations(cls, value: Any) -> Any:
        if value is None:
            return []
        return dedupe_strings(normalize_location_value(item) for item in value)

    @field_validator("country", mode="before")
    @classmethod
    def normalize_country(cls, value: Any) -> str:
        return normalize_country_code(value)

    @field_validator("work_arrangements", mode="before")
    @classmethod
    def normalize_work_arrangements(cls, value: Any) -> Any:
        return [normalize_work_arrangement(item) for item in (value or [])]

    @field_validator("employment_types", mode="before")
    @classmethod
    def normalize_employment_types(cls, value: Any) -> Any:
        return [normalize_employment_type(item) for item in (value or [])]

    @field_validator("visa_preferences", mode="before")
    @classmethod
    def normalize_visa_preferences(cls, value: Any) -> Any:
        return [normalize_visa_preference(item) for item in (value or [])]


class SkillPreference(PreferenceModel):
    name: PreferenceText
    category: CategoryText | None = None
    source: Literal["user", "candidate", "taxonomy", "bundle", "default"] = "user"
    confirmed: bool = True


class MatchPriorities(PreferenceModel):
    title_match: int = Field(default=25, ge=0, le=100)
    required_skill_match: int = Field(default=25, ge=0, le=100)
    industry_match: int = Field(default=20, ge=0, le=100)
    salary_match: int = Field(default=10, ge=0, le=100)
    work_arrangement_match: int = Field(default=10, ge=0, le=100)
    visa_signal_match: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def exact_total(self) -> "MatchPriorities":
        if sum(self.model_dump().values()) != 100:
            raise ValueError("match priorities must total exactly 100")
        return self


class PreferencesPayload(PreferenceModel):
    search_preferences: SearchPreferences = Field(default_factory=SearchPreferences)
    skills: list[SkillPreference] = Field(default_factory=list, max_length=200)
    skill_categories: list[CategoryText] = Field(default_factory=list, max_length=30)
    match_priorities: MatchPriorities = Field(default_factory=MatchPriorities)

    @field_validator("skill_categories", mode="after")
    @classmethod
    def dedupe_categories(cls, value: list[str]) -> list[str]:
        return dedupe_strings(value)

    @field_validator("skills", mode="after")
    @classmethod
    def dedupe_skills(cls, value: list[SkillPreference]) -> list[SkillPreference]:
        output: list[SkillPreference] = []
        seen: set[str] = set()
        for skill in value:
            key = skill.name.casefold()
            if key not in seen:
                seen.add(key)
                output.append(skill)
        return output


class GeneratedSearchTitle(PreferenceModel):
    title: PreferenceText
    variations: list[PreferenceText] = Field(default_factory=list, max_length=20)


class GeneratedSkillAlias(PreferenceModel):
    canonical: PreferenceText
    aliases: list[PreferenceText] = Field(default_factory=list, max_length=100)
    category: CategoryText | None = None
    source: str = Field(default="deterministic", min_length=1, max_length=40)
    confidence: float = Field(default=1.0, ge=0, le=1)


class GeneratedPreview(PreferenceModel):
    search_titles: list[GeneratedSearchTitle] = Field(default_factory=list, max_length=25)
    skill_aliases: list[GeneratedSkillAlias] = Field(default_factory=list, max_length=200)
    derived_candidate_profile: dict[str, Any] = Field(default_factory=dict)


class RevisionMetadata(PreferenceModel):
    bundle_uuid: UUID | None = None
    revision: int | None = Field(default=None, ge=1)
    config_revision_map: dict[str, int] = Field(default_factory=dict)
    generator_version: str = Field(default="preferences-v1", min_length=1, max_length=80)
    created_at: datetime | None = None


class RevisionHistoryItem(PreferenceModel):
    bundle_uuid: UUID
    revision: int = Field(ge=1)
    created_at: datetime
    generator_version: str
    source_ui_version: str | None = None
    status: str = "active"
    is_current: bool = False
    warnings: list[str] = Field(default_factory=list)


class PreferencesDocument(PreferencesPayload):
    generated_preview: GeneratedPreview = Field(default_factory=GeneratedPreview)
    revision: RevisionMetadata = Field(default_factory=RevisionMetadata)
    revision_history: list[RevisionHistoryItem] = Field(default_factory=list)
    profile_completeness: int = Field(default=0, ge=0, le=100)
    warnings: list[str] = Field(default_factory=list, max_length=100)
    is_confirmed: bool = False
