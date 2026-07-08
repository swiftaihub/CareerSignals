"""Visa sponsorship signal detection."""

from __future__ import annotations

import re

from src.config.schemas import VisaKeywords
from src.utils.text_cleaning import clean_text

CLEAR_POSITIVE_PATTERNS = (
    r"visa sponsorship (?:is )?(?:available|provided)",
    r"h-?1b sponsorship (?:is )?(?:available|provided)",
    r"\bwe (?:do )?sponsor\b",
    r"\bwe will sponsor\b",
    r"\bsponsor employment visas\b",
)


def _contains_phrase(text: str, phrase: str) -> bool:
    escaped = re.escape(phrase.casefold()).replace(r"\ ", r"\s+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def detect_visa_signal(description: str, visa_keywords: VisaKeywords) -> str:
    """Classify visa-sponsorship signal as Positive, Negative, or Unknown."""

    text = clean_text(description).casefold()
    if not text:
        return "Unknown"

    positive_hit = any(_contains_phrase(text, keyword) for keyword in visa_keywords.positive)
    negative_hit = any(_contains_phrase(text, keyword) for keyword in visa_keywords.negative)
    clear_positive = any(re.search(pattern, text) for pattern in CLEAR_POSITIVE_PATTERNS)

    if negative_hit and not clear_positive:
        return "Negative"
    if positive_hit or clear_positive:
        return "Positive"
    if negative_hit:
        return "Negative"
    return "Unknown"
