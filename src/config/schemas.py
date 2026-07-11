"""Typed platform, user, and normalized-job schemas for CareerSignals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfigModel(BaseModel):
    """Configuration base class that rejects undocumented input fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class GlobalFilters(StrictConfigModel):
    """Platform-owned filters used only while acquiring the shared job universe."""

    country: str = "US"
    locations: list[str] = Field(default_factory=list)
    work_type: list[str] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)


class FreshnessFilter(StrictConfigModel):
    enabled: bool = True
    max_post_age_hours: int = Field(default=24, gt=0, le=24 * 90)
    include_unknown_dates: bool = False


class JobCategoryConfig(StrictConfigModel):
    category_name: str = Field(min_length=1, max_length=160)
    search_titles: list[str] = Field(default_factory=list, max_length=100)
    industries: list[str] = Field(default_factory=list, max_length=100)
    seniority: list[str] = Field(default_factory=list, max_length=30)


class ConnectorRetryConfig(StrictConfigModel):
    timeout_seconds: float = Field(default=15, gt=0, le=120)
    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_seconds: float = Field(default=1, ge=0, le=60)


class ConnectorBudgetConfig(StrictConfigModel):
    page_limit: int = Field(default=1, ge=1, le=100)
    query_limit_per_category: int = Field(default=4, ge=1, le=100)


class ConnectorScheduleConfig(StrictConfigModel):
    cron: str = "0 */6 * * *"
    timezone: str = "UTC"
    stale_after_hours: int = Field(default=8, ge=1, le=24 * 30)


class PlatformConnectorConfig(StrictConfigModel):
    """System-only Connector acquisition configuration.

    This model is deliberately separate from every user-editable model.  It is
    loaded only from the repository-controlled platform YAML file.
    """

    enabled_sources: list[
        Literal["mock", "adzuna", "serpapi", "greenhouse", "lever", "usajobs"]
    ] = Field(default_factory=lambda: ["mock"])
    global_filters: GlobalFilters = Field(default_factory=GlobalFilters)
    freshness_filter: FreshnessFilter = Field(default_factory=FreshnessFilter)
    acquisition_categories: list[JobCategoryConfig] = Field(default_factory=list)
    source_budgets: dict[str, ConnectorBudgetConfig] = Field(default_factory=dict)
    retry: ConnectorRetryConfig = Field(default_factory=ConnectorRetryConfig)
    schedule: ConnectorScheduleConfig = Field(default_factory=ConnectorScheduleConfig)


class UserJobFilters(StrictConfigModel):
    """Preferences applied to the existing shared job universe."""

    country: str = "US"
    locations: list[str] = Field(default_factory=list, max_length=100)
    work_type: list[str] = Field(default_factory=list, max_length=20)
    employment_type: list[str] = Field(default_factory=list, max_length=20)
    visa_preferences: list[str] = Field(default_factory=list, max_length=20)
    excluded_companies: list[str] = Field(default_factory=list, max_length=200)
    excluded_titles: list[str] = Field(default_factory=list, max_length=200)


class RankingWeights(StrictConfigModel):
    title_match: float = Field(default=0.25, ge=0, le=1)
    required_skill_match: float = Field(default=0.25, ge=0, le=1)
    industry_match: float = Field(default=0.20, ge=0, le=1)
    salary_match: float = Field(default=0.10, ge=0, le=1)
    work_arrangement_match: float = Field(default=0.10, ge=0, le=1)
    visa_signal_match: float = Field(default=0.10, ge=0, le=1)

    @property
    def total(self) -> float:
        return (
            self.title_match
            + self.required_skill_match
            + self.industry_match
            + self.salary_match
            + self.work_arrangement_match
            + self.visa_signal_match
        )

    @model_validator(mode="after")
    def require_positive_total(self) -> "RankingWeights":
        if self.total <= 0:
            raise ValueError("at least one ranking weight must be greater than zero")
        return self


class OutputConfig(StrictConfigModel):
    excel_file: str = "outputs/job_search_tracker.xlsx"
    top_match_threshold: float = Field(default=80, ge=0, le=100)


class UserJobsConfig(StrictConfigModel):
    """User-editable job filtering and ranking configuration."""

    global_filters: UserJobFilters = Field(default_factory=UserJobFilters)
    job_categories: list[JobCategoryConfig] = Field(min_length=1, max_length=100)
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)
    output: OutputConfig = Field(default_factory=OutputConfig)


# Import compatibility for processing and Connector type hints.  New code should
# use ``UserJobsConfig`` explicitly.
JobsConfig = UserJobsConfig


class RequiredPreferences(StrictConfigModel):
    work_arrangement: list[str] = Field(default_factory=list, max_length=20)


class SalaryExpectation(StrictConfigModel):
    min_base_salary: float = Field(default=0, ge=0)
    preferred_base_salary: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def preferred_is_not_below_minimum(self) -> "SalaryExpectation":
        if self.preferred_base_salary and self.preferred_base_salary < self.min_base_salary:
            raise ValueError("preferred_base_salary cannot be below min_base_salary")
        return self


class VisaKeywords(StrictConfigModel):
    positive: list[str] = Field(default_factory=list, max_length=100)
    negative: list[str] = Field(default_factory=list, max_length=100)


class Candidate(StrictConfigModel):
    target_titles: list[str] = Field(default_factory=list, max_length=200)
    target_industries: list[str] = Field(default_factory=list, max_length=100)
    required_preferences: RequiredPreferences = Field(default_factory=RequiredPreferences)
    salary_expectation: SalaryExpectation = Field(default_factory=SalaryExpectation)
    visa_keywords: VisaKeywords = Field(default_factory=VisaKeywords)
    skills: dict[str, list[str]] = Field(default_factory=dict)

    def all_skills(self) -> list[str]:
        skills: list[str] = []
        for group_skills in self.skills.values():
            skills.extend(group_skills)
        return sorted(set(skills), key=str.casefold)

    def skill_group_lookup(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for group, skills in self.skills.items():
            for skill in skills:
                lookup[skill.casefold()] = group
        return lookup


class CandidateProfileConfig(StrictConfigModel):
    candidate: Candidate


class SkillAlias(StrictConfigModel):
    canonical: str = Field(min_length=1, max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=100)


class SkillTaxonomyConfig(StrictConfigModel):
    skill_aliases: dict[str, SkillAlias] = Field(default_factory=dict)


class EffectiveUserConfig(StrictConfigModel):
    candidate_profile: CandidateProfileConfig
    jobs_config: UserJobsConfig
    skill_taxonomy: SkillTaxonomyConfig


class NormalizedJob(BaseModel):
    job_id: str
    source: str
    source_job_id: str | None = None
    category_name: str
    job_title: str
    normalized_title: str
    company: str
    normalized_company: str = ""
    industry: str = "Unknown"
    location: str
    location_normalized: str = "Unknown"
    location_group: str = "Other or Unclassified"
    work_arrangement: str = "Unknown"
    employment_type: str = "full-time"
    seniority: str = "Unknown"
    salary_min: float | None = None
    salary_max: float | None = None
    salary_midpoint: float | None = None
    salary_range_text: str | None = None
    date_posted: str | None = None
    posted_at: str | None = None
    date_collected: str
    jd_post_link: str
    apply_link: str | None = None
    job_description: str
    normalized_description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_extracted_skills: list[str] = Field(default_factory=list)
    visa_signal: str = "Unknown"
    visa_status: str = "Unknown"
    visa_evidence: str | None = None
    visa_confidence: str = "Low"
    match_score: float = 0.0
    match_tier: str = "Low Priority"
    reasoning_summary: str = ""
    application_status: str = "Not Applied"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


@dataclass(frozen=True)
class LegacyJobsConfig:
    """Read-only compatibility view for pre-SaaS processing callers."""

    global_filters: GlobalFilters
    freshness_filter: FreshnessFilter
    job_categories: list[JobCategoryConfig]
    ranking_weights: RankingWeights
    output: OutputConfig


@dataclass(frozen=True)
class ConfigBundle:
    platform_connector: PlatformConnectorConfig
    user_jobs: UserJobsConfig
    jobs: LegacyJobsConfig
    candidate_profile: CandidateProfileConfig
    skill_taxonomy: SkillTaxonomyConfig
