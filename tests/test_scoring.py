from __future__ import annotations

from src.config.loader import load_configs
from src.processing.scoring import derive_match_tier, score_job


def test_match_tier_boundaries() -> None:
    assert derive_match_tier(90) == "Excellent Match"
    assert derive_match_tier(80) == "Strong Match"
    assert derive_match_tier(70) == "Good Match"
    assert derive_match_tier(60) == "Possible Match"
    assert derive_match_tier(59.9) == "Low Priority"


def test_score_job_rewards_target_alignment() -> None:
    configs = load_configs(".")
    category = configs.jobs.job_categories[0]
    candidate = configs.candidate_profile.candidate

    job = {
        "job_title": "Product Data Scientist",
        "industry": "Technology",
        "salary_midpoint": 140000,
        "work_arrangement": "Remote",
        "visa_signal": "Positive",
        "all_extracted_skills": ["Python", "SQL", "Spark", "product analytics"],
    }

    scored = score_job(job, candidate, category, configs.jobs.ranking_weights)

    assert scored["match_score"] >= 85
    assert scored["match_tier"] in {"Strong Match", "Excellent Match"}
    assert "Product Data Scientist" in scored["reasoning_summary"] or "Python" in scored["reasoning_summary"]
