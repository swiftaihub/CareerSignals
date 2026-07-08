from __future__ import annotations

from src.config.loader import load_configs
from src.processing.skill_extractor import RuleBasedSkillExtractor


def test_skill_extractor_uses_candidate_skills_and_aliases() -> None:
    configs = load_configs(".")
    extractor = RuleBasedSkillExtractor(
        configs.candidate_profile.candidate,
        configs.skill_taxonomy,
    )

    result = extractor.extract(
        "Required: Python, SQL, Microsoft Power BI, Apache Spark, data build tool, "
        "and credit risk analytics. Preferred: LookML and Airflow."
    )

    assert "Python" in result.all_extracted_skills
    assert "Power BI" in result.all_extracted_skills
    assert "Spark" in result.all_extracted_skills
    assert "dbt" in result.all_extracted_skills
    assert "Credit Risk" in result.all_extracted_skills
    assert "Looker" in result.preferred_skills
    assert "Airflow" in result.preferred_skills
