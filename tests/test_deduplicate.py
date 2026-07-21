from __future__ import annotations

from src.processing.deduplicate import deduplicate_jobs


def _job(
    job_id: str,
    *,
    title: str,
    company: str = "Example",
    location: str = "Remote",
    link: str = "",
) -> dict[str, str]:
    return {
        "job_id": job_id,
        "job_title": title,
        "company": company,
        "location": location,
        "jd_post_link": link,
    }


def test_deduplicate_jobs_limits_fuzzy_matching_to_company_location_bucket() -> None:
    records = [
        _job("1", title="Senior Analytics Engineer"),
        _job("2", title="Analytics Engineer Senior"),
        _job("3", title="Senior Analytics Engineer", location="New York, NY"),
        _job("4", title="Senior Analytics Engineer", company="Other"),
    ]

    deduped = deduplicate_jobs(records)

    assert [record["job_id"] for record in deduped] == ["1", "3", "4"]


def test_deduplicate_jobs_preserves_exact_id_and_link_behavior() -> None:
    records = [
        _job("1", title="Data Scientist", link="https://example.test/jobs/1"),
        _job("1", title="Different title", link="https://example.test/jobs/2"),
        _job("2", title="Different role", link="https://example.test/jobs/1"),
    ]

    deduped = deduplicate_jobs(records)

    assert deduped == [records[0]]
