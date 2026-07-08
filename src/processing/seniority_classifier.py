"""Rule-based seniority classification."""

from __future__ import annotations

import re

from src.utils.text_cleaning import clean_text


def _has(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def classify_seniority(title: str, description: str = "") -> str:
    """Classify seniority from a job title and description."""

    text = clean_text(f"{title} {description}")

    if _has(r"\b(director|vp|vice president)\b", text):
        return "Director"
    if _has(r"\b(manager|head of)\b", text):
        return "Manager"
    if _has(r"\b(principal|staff)\b", text):
        return "Principal"
    if _has(r"\b(lead|tech lead)\b", text):
        return "Lead"
    if _has(r"\b(senior|sr\.?|level iii|iii)\b", text):
        return "Senior"
    if _has(r"\b(entry[- ]level|junior|jr\.?|associate|0[- ]?2 years|new grad)\b", text):
        return "Entry-level"
    if _has(r"\b(mid[- ]level|intermediate|2[- ]?5 years|3\+ years)\b", text):
        return "Mid-level"
    return "Unknown"
