"""Job deduplication logic."""

from __future__ import annotations

from typing import Any

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - exercised only without optional dependency
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def token_sort_ratio(left: str, right: str) -> float:
            left_tokens = " ".join(sorted(left.casefold().split()))
            right_tokens = " ".join(sorted(right.casefold().split()))
            return SequenceMatcher(None, left_tokens, right_tokens).ratio() * 100

    fuzz = _FallbackFuzz()


def _norm(value: object) -> str:
    return str(value or "").strip().casefold()


def _is_company_title_location_duplicate(
    candidate: dict[str, Any],
    existing: dict[str, Any],
    threshold: float = 92,
) -> bool:
    same_company = _norm(candidate.get("company")) == _norm(existing.get("company"))
    same_location = _norm(candidate.get("location")) == _norm(existing.get("location"))
    if not same_company or not same_location:
        return False
    title_score = fuzz.token_sort_ratio(
        _norm(candidate.get("job_title")),
        _norm(existing.get("job_title")),
    )
    return title_score >= threshold


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate jobs by stable ID, post link, and similar title/company/location."""

    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_links: set[str] = set()

    for job in jobs:
        job_id = _norm(job.get("job_id"))
        link = _norm(job.get("jd_post_link"))

        if job_id and job_id in seen_ids:
            continue
        if link and link in seen_links:
            continue
        if any(_is_company_title_location_duplicate(job, existing) for existing in deduped):
            continue

        deduped.append(job)
        if job_id:
            seen_ids.add(job_id)
        if link:
            seen_links.add(link)

    return deduped
