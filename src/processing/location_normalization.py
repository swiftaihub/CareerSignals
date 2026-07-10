"""Location normalization and grouping for job filters."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Iterable

from src.utils.text_cleaning import clean_text

REMOTE_GROUP = "Remote"
MULTI_LOCATION_GROUP = "Nationwide or Multiple Locations"
NORTHEAST_GROUP = "Northeast"
MIDWEST_GROUP = "Midwest"
SOUTH_GROUP = "South"
WEST_GROUP = "West"
INTERNATIONAL_GROUP = "International"
OTHER_GROUP = "Other or Unclassified"

LOCATION_GROUP_ORDER = (
    REMOTE_GROUP,
    MULTI_LOCATION_GROUP,
    NORTHEAST_GROUP,
    MIDWEST_GROUP,
    SOUTH_GROUP,
    WEST_GROUP,
    INTERNATIONAL_GROUP,
    OTHER_GROUP,
)

STATE_ABBREVIATIONS: dict[str, str] = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "washington dc": "DC",
    "washington d c": "DC",
    "washington, dc": "DC",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}

US_STATE_ABBREVIATIONS = set(STATE_ABBREVIATIONS.values())

STATE_REGIONS: dict[str, str] = {
    **{state: NORTHEAST_GROUP for state in ("CT", "DC", "ME", "MA", "NH", "NJ", "NY", "PA", "RI", "VT")},
    **{state: MIDWEST_GROUP for state in ("IA", "IL", "IN", "KS", "MI", "MN", "MO", "ND", "NE", "OH", "SD", "WI")},
    **{state: SOUTH_GROUP for state in ("AL", "AR", "DE", "FL", "GA", "KY", "LA", "MD", "MS", "NC", "OK", "SC", "TN", "TX", "VA", "WV")},
    **{state: WEST_GROUP for state in ("AK", "AZ", "CA", "CO", "HI", "ID", "MT", "NM", "NV", "OR", "UT", "WA", "WY")},
}

CITY_ALIASES: dict[str, str] = {
    "nyc": "New York, NY",
    "new york city": "New York, NY",
    "washington dc": "Washington, DC",
    "washington d c": "Washington, DC",
}

INTERNATIONAL_HINTS = {
    "australia",
    "brazil",
    "canada",
    "china",
    "denmark",
    "france",
    "germany",
    "india",
    "ireland",
    "italy",
    "japan",
    "mexico",
    "netherlands",
    "philippines",
    "poland",
    "portugal",
    "qatar",
    "singapore",
    "spain",
    "sweden",
    "taiwan",
    "united kingdom",
    "uk",
}

REMOTE_RE = re.compile(r"\b(remote|distributed)\b", re.IGNORECASE)
MULTI_RE = re.compile(
    r"\b(multiple locations|various locations|nationwide|anywhere|field united states|"
    r"united states remote|usa remote|us remote|united states\s*$|usa\s*$|us\s*$|n/a)\b",
    re.IGNORECASE,
)
PUNCTUATION_RE = re.compile(r"\s*[,;/|]\s*")
REPEATED_PUNCTUATION_RE = re.compile(r"([,;])\1+")
CITY_STATE_COMMA_RE = re.compile(r"^(?P<city>[a-z .'-]+),\s*(?P<state>[a-z .]+)(?:,\s*(?:us|usa|united states|united states of america))?$", re.IGNORECASE)
CITY_STATE_SPACE_RE = re.compile(r"^(?P<city>[a-z .'-]+?)\s+(?P<state>[A-Z]{2})$", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizedLocation:
    original: str
    normalized: str
    group: str


def _clean_location(value: object) -> str:
    text = clean_text(value)
    text = text.replace("•", ",").replace("–", "-").replace("—", "-")
    text = REPEATED_PUNCTUATION_RE.sub(r"\1", text)
    text = PUNCTUATION_RE.sub(", ", text)
    return re.sub(r"\s+", " ", text).strip(" ,")


def _title_city(value: str) -> str:
    small_words = {"of", "and", "the"}
    words = []
    for word in value.split():
        if word.casefold() in small_words:
            words.append(word.casefold())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _state_abbreviation(value: str) -> str | None:
    cleaned = re.sub(r"[^a-zA-Z ]+", " ", value).strip().casefold()
    if not cleaned:
        return None
    upper = cleaned.upper()
    if upper in US_STATE_ABBREVIATIONS:
        return upper
    return STATE_ABBREVIATIONS.get(cleaned)


def _group_for_state(state: str | None) -> str:
    if not state:
        return OTHER_GROUP
    return STATE_REGIONS.get(state, OTHER_GROUP)


def _looks_international(text: str) -> bool:
    lowered = text.casefold()
    if any(hint in lowered for hint in INTERNATIONAL_HINTS):
        if not re.search(r"\b(?:us|u\.s\.|usa|united states|united states of america)\b", lowered):
            return True
        if re.search(r"\b(canada|united kingdom|india|ireland|singapore|australia|brazil|mexico)\b", lowered):
            return True
    return False


def _parse_city_state(text: str) -> tuple[str, str] | None:
    alias_key = re.sub(r"\s+", " ", text.casefold().replace(".", "").replace(",", " ")).strip()
    alias = CITY_ALIASES.get(alias_key)
    if alias:
        city, state = alias.split(", ")
        return city, state

    comma_match = CITY_STATE_COMMA_RE.match(text)
    if comma_match:
        state = _state_abbreviation(comma_match.group("state"))
        if state:
            return _title_city(comma_match.group("city").strip()), state

    space_match = CITY_STATE_SPACE_RE.match(text)
    if space_match:
        state = _state_abbreviation(space_match.group("state"))
        if state:
            return _title_city(space_match.group("city").strip()), state

    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        state = _state_abbreviation(parts[1])
        if state:
            return _title_city(parts[0]), state

    state_only = _state_abbreviation(text)
    if state_only:
        return text.upper() if len(text.strip()) == 2 else _title_city(text), state_only

    return None


def normalize_location(value: object) -> NormalizedLocation:
    """Normalize a source location into a display value and broad group."""

    original = clean_text(value) or "Unknown"
    text = _clean_location(original)
    if not text or text.casefold() == "unknown":
        return NormalizedLocation(original=original, normalized="Unknown", group=OTHER_GROUP)

    if REMOTE_RE.search(text):
        return NormalizedLocation(original=original, normalized="Remote", group=REMOTE_GROUP)

    if MULTI_RE.search(text) or text.count(",") >= 3:
        return NormalizedLocation(
            original=original,
            normalized="Multiple Locations",
            group=MULTI_LOCATION_GROUP,
        )

    parsed = _parse_city_state(text)
    if parsed:
        city, state = parsed
        if len(city) == 2 and city.upper() == state:
            normalized = state
        else:
            normalized = f"{city}, {state}"
        return NormalizedLocation(
            original=original,
            normalized=normalized,
            group=_group_for_state(state),
        )

    if _looks_international(text):
        return NormalizedLocation(original=original, normalized=text, group=INTERNATIONAL_GROUP)

    return NormalizedLocation(original=original, normalized=text, group=OTHER_GROUP)


def location_search_text(value: object) -> str:
    normalized = normalize_location(value)
    return f"{normalized.original} {normalized.normalized} {normalized.group}".casefold()


def build_location_facets(locations: Iterable[object]) -> dict[str, list[dict[str, object]]]:
    value_counts: Counter[tuple[str, str]] = Counter()
    group_counts: Counter[str] = Counter()

    for value in locations:
        normalized = normalize_location(value)
        if normalized.normalized == "Unknown" and normalized.group == OTHER_GROUP:
            continue
        value_counts[(normalized.group, normalized.normalized)] += 1
        group_counts[normalized.group] += 1

    locations_payload = [
        {"group": group, "value": value, "count": count}
        for (group, value), count in sorted(
            value_counts.items(),
            key=lambda item: (
                LOCATION_GROUP_ORDER.index(item[0][0])
                if item[0][0] in LOCATION_GROUP_ORDER
                else len(LOCATION_GROUP_ORDER),
                item[0][1].casefold(),
            ),
        )
    ]
    groups_payload = [
        {"group": group, "count": group_counts[group]}
        for group in LOCATION_GROUP_ORDER
        if group_counts[group]
    ]
    return {"locations": locations_payload, "location_groups": groups_payload}
