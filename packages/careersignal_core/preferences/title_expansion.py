"""Conservative deterministic job-title expansion."""

from __future__ import annotations

import re
from typing import Iterable

from packages.careersignal_core.preferences.normalization import dedupe_strings, sanitize_text


TITLE_GENERATOR_VERSION = "title-rules-v1"

_FORWARD_REPLACEMENTS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"\bsenior\b", re.IGNORECASE), ("Sr", "Sr.")),
    (re.compile(r"\bjunior\b", re.IGNORECASE), ("Jr", "Jr.")),
    (re.compile(r"\bvice president\b", re.IGNORECASE), ("VP",)),
    (re.compile(r"\bregistered nurse\b", re.IGNORECASE), ("RN",)),
    (re.compile(r"\bnurse practitioner\b", re.IGNORECASE), ("NP",)),
    (re.compile(r"\bchief executive officer\b", re.IGNORECASE), ("CEO",)),
    (re.compile(r"\bchief financial officer\b", re.IGNORECASE), ("CFO",)),
    (re.compile(r"\bchief operating officer\b", re.IGNORECASE), ("COO",)),
    (re.compile(r"\bhuman resources\b", re.IGNORECASE), ("HR",)),
    (re.compile(r"\bquality assurance\b", re.IGNORECASE), ("QA",)),
)
_REVERSE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsr\.?\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\bjr\.?\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\bvp\b", re.IGNORECASE), "Vice President"),
    (re.compile(r"\brn\b", re.IGNORECASE), "Registered Nurse"),
    (re.compile(r"\bnp\b", re.IGNORECASE), "Nurse Practitioner"),
    (re.compile(r"\bceo\b", re.IGNORECASE), "Chief Executive Officer"),
    (re.compile(r"\bcfo\b", re.IGNORECASE), "Chief Financial Officer"),
    (re.compile(r"\bcoo\b", re.IGNORECASE), "Chief Operating Officer"),
)


def _comparison_key(value: str) -> str:
    text = sanitize_text(value)
    for pattern, replacement in _REVERSE_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def expand_job_title(
    title: str,
    *,
    observed_titles: Iterable[str] = (),
    max_variations: int = 12,
) -> list[str]:
    """Return narrow lexical equivalents with the submitted title first."""

    original = sanitize_text(title)
    if not original:
        return []
    variants: list[str] = [original]

    for pattern, replacements in _FORWARD_REPLACEMENTS:
        if not pattern.search(original):
            continue
        for replacement in replacements:
            variants.append(pattern.sub(replacement, original))

    for pattern, replacement in _REVERSE_REPLACEMENTS:
        if pattern.search(original):
            variants.append(pattern.sub(replacement, original))

    if "-" in original:
        variants.append(re.sub(r"\s*-\s*", " ", original))
    if "/" in original:
        variants.append(re.sub(r"\s*/\s*", " ", original))

    comparison_key = _comparison_key(original)
    equivalent_observed = sorted(
        {
            sanitize_text(candidate)
            for candidate in observed_titles
            if sanitize_text(candidate)
            and _comparison_key(candidate) == comparison_key
        },
        key=str.casefold,
    )
    variants.extend(equivalent_observed)
    return dedupe_strings(variants)[:max_variations]


class JobTitleExpansionService:
    version = TITLE_GENERATOR_VERSION

    def expand(self, title: str, *, observed_titles: Iterable[str] = ()) -> list[str]:
        return expand_job_title(title, observed_titles=observed_titles)
