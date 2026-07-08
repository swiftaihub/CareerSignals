"""Work-arrangement detection."""

from __future__ import annotations

import re

from src.utils.text_cleaning import clean_text


def detect_work_arrangement(title: str, location: str, description: str) -> str:
    """Detect Remote, Hybrid, On-site, or Unknown from job text."""

    title_text = clean_text(title).casefold()
    location_text = clean_text(location).casefold()
    description_text = clean_text(description).casefold()
    combined = f"{title_text} {location_text} {description_text}"

    if location_text == "remote" or re.search(r"\bremote\b", title_text):
        return "Remote"
    if re.search(r"\bhybrid\b", combined):
        return "Hybrid"
    if re.search(r"\bremote\b", combined) and not re.search(r"\b(not remote|no remote)\b", combined):
        return "Remote"
    if re.search(
        r"\b(on[- ]?site|onsite|in office|office based|office-based|5 days in office|not remote)\b",
        combined,
    ):
        return "On-site"
    return "Unknown"
