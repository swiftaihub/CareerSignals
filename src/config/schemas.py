"""Typed configuration and job schemas for CareerSignal."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class GlobalFilters(BaseModel):
    country: str = "US"
    locations: list[str] = Field(default_factory=list)
    work_type: list[str] = Field(default_factory=list)
    employment_type: list[str] = Field(default_factory=list)


class JobCategoryConfig(BaseModel):
    category_name: str
    search_titles: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)


class RankingWeights(BaseModel):
    title_match: float = 0.25
    required_skill_match: float = 0.25
    industry_match: float = 0.20
    salary_match: float = 0.10
    work_arrangement_match: float = 0.10
    visa_signal_match: float = 0.10

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


class OutputConfig(BaseModel):
    excel_file: str = "outputs/job_search_tracker.xlsx"
    top_match_threshold: float = 80


class JobsConfig(BaseModel):
    global_filters: GlobalFilters
    job_categories: list[JobCategoryConfig]
    ranking_weights: RankingWeights
    output: OutputConfig


class RequiredPreferences(BaseModel):
    work_arrangement: list[str] = Field(default_factory=list)


class SalaryExpectation(BaseModel):
    min_base_salary: float = 0
    preferred_base_salary: float = 0


class VisaKeywords(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)


class Candidate(BaseModel):
    target_titles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
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


class CandidateProfileConfig(BaseModel):
    candidate: Candidate


class SkillAlias(BaseModel):
    canonical: str
    aliases: list[str] = Field(default_factory=list)


class SkillTaxonomyConfig(BaseModel):
    skill_aliases: dict[str, SkillAlias] = Field(default_factory=dict)


class NormalizedJob(BaseModel):
    job_id: str
    source: str
    category_name: str
    job_title: str
    normalized_title: str
    company: str
    industry: str = "Unknown"
    location: str
    work_arrangement: str = "Unknown"
    employment_type: str = "full-time"
    seniority: str = "Unknown"
    salary_min: float | None = None
    salary_max: float | None = None
    salary_midpoint: float | None = None
    salary_range_text: str | None = None
    date_posted: str | None = None
    date_collected: str
    jd_post_link: str
    apply_link: str | None = None
    job_description: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    all_extracted_skills: list[str] = Field(default_factory=list)
    visa_signal: str = "Unknown"
    match_score: float = 0.0
    match_tier: str = "Low Priority"
    reasoning_summary: str = ""
    application_status: str = "Not Applied"

    def to_dict(self) -> dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump()
        return self.dict()


@dataclass(frozen=True)
class ConfigBundle:
    jobs: JobsConfig
    candidate_profile: CandidateProfileConfig
    skill_taxonomy: SkillTaxonomyConfig
