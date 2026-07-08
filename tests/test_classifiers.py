from __future__ import annotations

from src.processing.seniority_classifier import classify_seniority
from src.processing.work_arrangement import detect_work_arrangement


def test_seniority_classifier_detects_senior() -> None:
    assert classify_seniority("Senior Analytics Engineer") == "Senior"


def test_seniority_classifier_detects_entry_level() -> None:
    assert classify_seniority("Data Analyst", "Great for junior analysts with 0-2 years.") == "Entry-level"


def test_work_arrangement_detects_remote() -> None:
    assert detect_work_arrangement("Data Scientist - Remote", "Remote", "") == "Remote"


def test_work_arrangement_detects_hybrid() -> None:
    assert detect_work_arrangement("BI Analyst", "Wilmington, DE", "Hybrid Tuesday to Thursday.") == "Hybrid"


def test_work_arrangement_detects_on_site() -> None:
    assert detect_work_arrangement("Risk Analyst", "New York, NY", "This is an on-site role.") == "On-site"
