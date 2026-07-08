"""CareerSignal match scoring."""

from __future__ import annotations

from typing import Any

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - exercised only without optional dependency
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def WRatio(left: str, right: str) -> float:
            return SequenceMatcher(None, left.casefold(), right.casefold()).ratio() * 100

    fuzz = _FallbackFuzz()

from src.config.schemas import Candidate, JobCategoryConfig, RankingWeights


def derive_match_tier(match_score: float) -> str:
    if match_score >= 90:
        return "Excellent Match"
    if match_score >= 80:
        return "Strong Match"
    if match_score >= 70:
        return "Good Match"
    if match_score >= 60:
        return "Possible Match"
    return "Low Priority"


def _norm(value: object) -> str:
    return str(value or "").strip().casefold()


def _best_fuzzy_score(value: str, choices: list[str]) -> float:
    if not value or not choices:
        return 0.0
    return max(float(fuzz.WRatio(value, choice)) for choice in choices)


def _title_score(job: dict[str, Any], candidate: Candidate, category: JobCategoryConfig) -> float:
    choices = list(dict.fromkeys([*candidate.target_titles, *category.search_titles]))
    return _best_fuzzy_score(str(job.get("job_title") or ""), choices)


def _skill_score(job: dict[str, Any], candidate: Candidate) -> float:
    job_skills = {_norm(skill) for skill in job.get("all_extracted_skills", []) if _norm(skill)}
    candidate_skills = {_norm(skill) for skill in candidate.all_skills()}

    if not job_skills:
        return 40.0

    matched = job_skills & candidate_skills
    return min(100.0, (len(matched) / len(job_skills)) * 100)


def _industry_score(job: dict[str, Any], candidate: Candidate) -> float:
    industry = _norm(job.get("industry"))
    targets = [_norm(industry_name) for industry_name in candidate.target_industries]
    if not industry:
        return 40.0
    if industry in targets:
        return 100.0
    if any(industry in target or target in industry for target in targets):
        return 90.0
    fuzzy_score = _best_fuzzy_score(industry, targets)
    return min(85.0, fuzzy_score)


def _salary_score(job: dict[str, Any], candidate: Candidate) -> float:
    midpoint = job.get("salary_midpoint")
    if midpoint is None:
        return 50.0

    min_salary = candidate.salary_expectation.min_base_salary
    preferred_salary = candidate.salary_expectation.preferred_base_salary
    midpoint = float(midpoint)

    if preferred_salary and midpoint >= preferred_salary:
        return 100.0
    if min_salary and midpoint >= min_salary:
        span = max(preferred_salary - min_salary, 1)
        return 75.0 + min(25.0, ((midpoint - min_salary) / span) * 25.0)
    if min_salary:
        return max(0.0, min(70.0, (midpoint / min_salary) * 70.0))
    return 50.0


def _work_arrangement_score(job: dict[str, Any], candidate: Candidate) -> float:
    work_arrangement = _norm(job.get("work_arrangement"))
    preferred = {
        _norm(value) for value in candidate.required_preferences.work_arrangement if _norm(value)
    }
    if not work_arrangement or work_arrangement == "unknown":
        return 50.0
    if work_arrangement in preferred:
        return 100.0
    if work_arrangement == "on-site":
        return 20.0
    return 50.0


def _visa_score(job: dict[str, Any]) -> float:
    signal = _norm(job.get("visa_signal"))
    if signal == "positive":
        return 100.0
    if signal == "negative":
        return 10.0
    return 60.0


def _matched_candidate_skills(job: dict[str, Any], candidate: Candidate) -> list[str]:
    candidate_skills = {_norm(skill): skill for skill in candidate.all_skills()}
    matched = [
        candidate_skills[_norm(skill)]
        for skill in job.get("all_extracted_skills", [])
        if _norm(skill) in candidate_skills
    ]
    return sorted(set(matched), key=str.casefold)


def _format_salary_context(job: dict[str, Any], candidate: Candidate) -> str:
    midpoint = job.get("salary_midpoint")
    if midpoint is None:
        return "Salary was not listed"
    if midpoint >= candidate.salary_expectation.preferred_base_salary:
        return "salary is at or above the preferred range"
    if midpoint >= candidate.salary_expectation.min_base_salary:
        return "salary meets the minimum target"
    return "salary appears below the target range"


def build_reasoning_summary(job: dict[str, Any], candidate: Candidate) -> str:
    tier = derive_match_tier(float(job.get("match_score") or 0))
    matched_skills = _matched_candidate_skills(job, candidate)
    skill_text = ", ".join(matched_skills[:6]) if matched_skills else "limited target skills"
    industry = job.get("industry") or "Unknown"
    salary_context = _format_salary_context(job, candidate)
    work_arrangement = job.get("work_arrangement") or "Unknown"
    visa_signal = job.get("visa_signal") or "Unknown"

    if tier == "Low Priority":
        opener = "Lower-priority match"
    else:
        opener = f"{tier.replace(' Match', '')} match"

    return (
        f"{opener} because the role aligns with {skill_text} in {industry}. "
        f"{salary_context}, work arrangement is {work_arrangement}, and visa "
        f"sponsorship signal is {visa_signal}."
    )


def score_job(
    job: dict[str, Any],
    candidate: Candidate,
    category_config: JobCategoryConfig,
    weights: RankingWeights,
) -> dict[str, Any]:
    """Score a normalized and enriched job against the candidate profile."""

    components = {
        "title_match": _title_score(job, candidate, category_config),
        "required_skill_match": _skill_score(job, candidate),
        "industry_match": _industry_score(job, candidate),
        "salary_match": _salary_score(job, candidate),
        "work_arrangement_match": _work_arrangement_score(job, candidate),
        "visa_signal_match": _visa_score(job),
    }
    weighted_total = (
        components["title_match"] * weights.title_match
        + components["required_skill_match"] * weights.required_skill_match
        + components["industry_match"] * weights.industry_match
        + components["salary_match"] * weights.salary_match
        + components["work_arrangement_match"] * weights.work_arrangement_match
        + components["visa_signal_match"] * weights.visa_signal_match
    )
    denominator = weights.total or 1.0
    match_score = round(weighted_total / denominator, 1)

    scored = {**job, "match_score": match_score, "match_tier": derive_match_tier(match_score)}
    scored["reasoning_summary"] = build_reasoning_summary(scored, candidate)
    return scored
