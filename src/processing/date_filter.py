"""Posted-date parsing and freshness filtering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any

from src.config.schemas import FreshnessFilter
from src.utils.text_cleaning import clean_text

RELATIVE_RE = re.compile(
    r"(?P<quantity>\d+)\+?\s*(?P<unit>minute|hour|day|week|month)s?\s+ago",
    re.IGNORECASE,
)
DATE_ONLY_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y")


@dataclass(frozen=True)
class ParsedPostedDate:
    posted_at: datetime
    date_only: bool = False


@dataclass(frozen=True)
class FreshnessDecision:
    keep: bool
    reason: str
    parsed_posted_at: datetime | None = None


def _aware_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current


def _with_timezone(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=reference.tzinfo or timezone.utc)
    return value.astimezone(reference.tzinfo or timezone.utc)


def parse_posted_date(value: Any, now: datetime | None = None) -> ParsedPostedDate | None:
    """Parse common source posted-date strings into an aware datetime."""

    text = clean_text(value)
    if not text:
        return None

    current = _aware_now(now)
    normalized = text.casefold()

    if normalized in {"today", "just now", "just posted"}:
        return ParsedPostedDate(current)
    if normalized == "yesterday":
        return ParsedPostedDate(current - timedelta(days=1))

    relative_match = RELATIVE_RE.search(normalized)
    if relative_match:
        quantity = int(relative_match.group("quantity"))
        unit = relative_match.group("unit").casefold()
        if unit == "minute":
            delta = timedelta(minutes=quantity)
        elif unit == "hour":
            delta = timedelta(hours=quantity)
        elif unit == "day":
            delta = timedelta(days=quantity)
        elif unit == "week":
            delta = timedelta(weeks=quantity)
        else:
            delta = timedelta(days=quantity * 30)
        return ParsedPostedDate(current - delta)

    for date_format in DATE_ONLY_FORMATS:
        try:
            parsed_date = datetime.strptime(text, date_format).date()
        except ValueError:
            continue
        posted_at = datetime.combine(parsed_date, time.min, tzinfo=current.tzinfo)
        return ParsedPostedDate(posted_at, date_only=True)

    iso_text = text.replace("Z", "+00:00")
    try:
        parsed_datetime = datetime.fromisoformat(iso_text)
        return ParsedPostedDate(_with_timezone(parsed_datetime, current))
    except ValueError:
        pass

    return None


def freshness_decision(
    job: dict[str, Any],
    freshness_filter: FreshnessFilter,
    now: datetime | None = None,
) -> FreshnessDecision:
    """Return whether a job should be kept under the configured freshness filter."""

    if not freshness_filter.enabled:
        return FreshnessDecision(True, "disabled")

    current = _aware_now(now)
    parsed = parse_posted_date(job.get("date_posted"), current)
    if parsed is None:
        if freshness_filter.include_unknown_dates:
            return FreshnessDecision(True, "unknown_date_included")
        return FreshnessDecision(False, "unknown_date_excluded")

    cutoff = current - timedelta(hours=freshness_filter.max_post_age_hours)
    if parsed.date_only:
        posted_date: date = parsed.posted_at.date()
        if posted_date >= cutoff.date():
            return FreshnessDecision(True, "fresh_date_only", parsed.posted_at)
        return FreshnessDecision(False, "older_than_max_age", parsed.posted_at)

    if parsed.posted_at >= cutoff:
        return FreshnessDecision(True, "fresh", parsed.posted_at)
    return FreshnessDecision(False, "older_than_max_age", parsed.posted_at)


def filter_jobs_by_posted_date(
    jobs: list[dict[str, Any]],
    freshness_filter: FreshnessFilter,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Filter jobs to the configured maximum posted-date age."""

    stats = {
        "input_jobs": len(jobs),
        "kept_jobs": 0,
        "older_than_max_age": 0,
        "unknown_date_excluded": 0,
        "unknown_date_included": 0,
        "disabled": 0,
    }
    kept: list[dict[str, Any]] = []

    for job in jobs:
        decision = freshness_decision(job, freshness_filter, now)
        stats[decision.reason] = stats.get(decision.reason, 0) + 1
        if decision.keep:
            kept.append(job)

    stats["kept_jobs"] = len(kept)
    return kept, stats
