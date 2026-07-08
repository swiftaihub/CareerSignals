from __future__ import annotations

from src.config.loader import load_configs


def test_load_configs_reads_expected_categories() -> None:
    configs = load_configs(".")

    category_names = {category.category_name for category in configs.jobs.job_categories}

    assert "Data Scientist - Tech" in category_names
    assert "Credit Risk Analyst" in category_names
    assert configs.jobs.output.excel_file == "outputs/job_search_tracker.xlsx"
    assert "Python" in configs.candidate_profile.candidate.all_skills()
