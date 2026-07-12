"""Static option catalogs for the friendly Settings API."""

from __future__ import annotations

from typing import Iterable

from packages.careersignal_core.preferences.normalization import country_options, sanitize_text


SENIORITY_LEVELS = (
    "Internship",
    "Entry Level",
    "Associate",
    "Mid Level",
    "Senior",
    "Lead",
    "Staff",
    "Principal",
    "Manager",
    "Senior Manager",
    "Director",
    "Senior Director",
    "Vice President",
    "Executive",
)
EMPLOYMENT_TYPES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contract", "Contract"),
    ("temporary", "Temporary"),
    ("internship", "Internship"),
    ("apprenticeship", "Apprenticeship"),
    ("freelance", "Freelance"),
    ("other", "Other"),
)
WORK_ARRANGEMENTS = (
    ("remote", "Remote"),
    ("hybrid", "Hybrid"),
    ("on_site", "On-site"),
)
VISA_OPTIONS = (
    ("sponsorship_required", "Sponsorship required"),
    ("h1b_transfer_required", "H-1B transfer required"),
    ("sponsorship_preferred", "Sponsorship preferred"),
    ("no_sponsorship_required", "No sponsorship required"),
    ("regardless", "Open regardless of sponsorship signal"),
)


def option_items(values: Iterable[tuple[str, str] | str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for value in values:
        if isinstance(value, tuple):
            option_value, label = value
        else:
            option_value = label = value
        rows.append({"value": sanitize_text(option_value), "label": sanitize_text(label)})
    return rows


def fixed_options() -> dict[str, list[dict[str, str]]]:
    return {
        "countries": option_items(country_options()),
        "seniority_levels": option_items(SENIORITY_LEVELS),
        "employment_types": option_items(EMPLOYMENT_TYPES),
        "work_arrangements": option_items(WORK_ARRANGEMENTS),
        "visa_options": option_items(VISA_OPTIONS),
    }
