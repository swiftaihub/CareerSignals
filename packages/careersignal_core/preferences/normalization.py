"""Deterministic normalization for user-entered preference values."""

from __future__ import annotations

from functools import lru_cache
import html
import re
import unicodedata
from typing import Any, Iterable

from babel import Locale


HTML_TAG_RE = re.compile(r"<[^>]*>")
WHITESPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^a-z0-9]+")

WORK_ARRANGEMENT_ALIASES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on site": "on_site",
    "onsite": "on_site",
    "on-site": "on_site",
    "on_site": "on_site",
}
EMPLOYMENT_TYPE_ALIASES = {
    "full time": "full_time",
    "full-time": "full_time",
    "full_time": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "part_time": "part_time",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
    "apprenticeship": "apprenticeship",
    "freelance": "freelance",
    "other": "other",
}
VISA_PREFERENCE_ALIASES = {
    "sponsorship required": "sponsorship_required",
    "sponsorship_required": "sponsorship_required",
    "h-1b transfer required": "h1b_transfer_required",
    "h1b transfer required": "h1b_transfer_required",
    "h1b_transfer_required": "h1b_transfer_required",
    "sponsorship preferred": "sponsorship_preferred",
    "sponsorship_preferred": "sponsorship_preferred",
    "no sponsorship required": "no_sponsorship_required",
    "no_sponsorship_required": "no_sponsorship_required",
    "open to roles regardless of sponsorship signal": "regardless",
    "regardless": "regardless",
}


def sanitize_text(value: Any) -> str:
    """Strip markup/control characters and normalize whitespace."""

    if value is None:
        return ""
    text = html.unescape(str(value))
    text = HTML_TAG_RE.sub(" ", text)
    text = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cf"} else character
        for character in text
    )
    return WHITESPACE_RE.sub(" ", text.replace("\u00a0", " ")).strip()


def normalized_key(value: Any) -> str:
    return sanitize_text(value).casefold()


def dedupe_strings(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = sanitize_text(value)
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def canonical_code(value: Any, aliases: dict[str, str]) -> str:
    text = sanitize_text(value)
    key = WHITESPACE_RE.sub(" ", text.replace("_", " ")).casefold()
    if key in aliases:
        return aliases[key]
    original_key = text.casefold()
    return aliases.get(original_key, original_key.replace("-", "_").replace(" ", "_"))


def normalize_work_arrangement(value: Any) -> str:
    return canonical_code(value, WORK_ARRANGEMENT_ALIASES)


def normalize_employment_type(value: Any) -> str:
    return canonical_code(value, EMPLOYMENT_TYPE_ALIASES)


def normalize_visa_preference(value: Any) -> str:
    return canonical_code(value, VISA_PREFERENCE_ALIASES)


@lru_cache(maxsize=1)
def country_options() -> tuple[tuple[str, str], ...]:
    """Return ISO alpha-2 countries from Babel's CLDR dataset."""

    territories = Locale.parse("en").territories
    rows = [
        (str(code).upper(), sanitize_text(name))
        for code, name in territories.items()
        if isinstance(code, str) and len(code) == 2 and code.isalpha() and name
    ]
    return tuple(sorted(rows, key=lambda row: (row[1].casefold(), row[0])))


@lru_cache(maxsize=1)
def _country_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for code, name in country_options():
        lookup[code.casefold()] = code
        lookup[name.casefold()] = code
    lookup.update(
        {
            "usa": "US",
            "u.s.": "US",
            "united states of america": "US",
            "uk": "GB",
            "u.k.": "GB",
        }
    )
    return lookup


def normalize_country_code(value: Any) -> str:
    text = sanitize_text(value)
    if not text:
        return "US"
    return _country_lookup().get(text.casefold(), text.upper())


def slugify(value: Any, *, fallback: str = "item") -> str:
    text = sanitize_text(value)
    replacements = {
        "C++": "C plus plus",
        "c++": "c plus plus",
        "C#": "C sharp",
        "c#": "c sharp",
        ".NET": "dotnet",
        ".net": "dotnet",
    }
    text = replacements.get(text, text)
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    slug = NON_WORD_RE.sub("_", ascii_text.casefold()).strip("_")
    return slug or fallback


def normalize_location_value(value: Any) -> str:
    """Normalize safe display spelling without forcing a US-only location model."""

    text = sanitize_text(value).strip(" ,;|")
    text = re.sub(r"\s*[,;|]\s*", ", ", text)
    return WHITESPACE_RE.sub(" ", text).strip(" ,")
