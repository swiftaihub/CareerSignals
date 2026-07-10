from __future__ import annotations

from src.processing.location_normalization import (
    INTERNATIONAL_GROUP,
    MIDWEST_GROUP,
    MULTI_LOCATION_GROUP,
    NORTHEAST_GROUP,
    OTHER_GROUP,
    REMOTE_GROUP,
    SOUTH_GROUP,
    WEST_GROUP,
    build_location_facets,
    normalize_location,
)


def test_normalizes_city_state_variants() -> None:
    cases = [
        ("New York, New York", "New York, NY", NORTHEAST_GROUP),
        ("NYC", "New York, NY", NORTHEAST_GROUP),
        ("Austin TX", "Austin, TX", SOUTH_GROUP),
        ("Chicago, Illinois", "Chicago, IL", MIDWEST_GROUP),
        ("San Francisco, CA", "San Francisco, CA", WEST_GROUP),
        ("Washington, D.C.", "Washington, DC", NORTHEAST_GROUP),
    ]

    for raw, normalized, group in cases:
        result = normalize_location(raw)
        assert result.normalized == normalized
        assert result.group == group


def test_detects_remote_and_multi_location_postings() -> None:
    remote = normalize_location("United States - Remote")
    multi = normalize_location("Multiple Locations")

    assert remote.normalized == "Remote"
    assert remote.group == REMOTE_GROUP
    assert multi.normalized == "Multiple Locations"
    assert multi.group == MULTI_LOCATION_GROUP


def test_detects_international_and_unknown_locations() -> None:
    international = normalize_location("Toronto, Canada")
    unknown = normalize_location("Greater Foobar Area")

    assert international.group == INTERNATIONAL_GROUP
    assert unknown.group == OTHER_GROUP
    assert unknown.normalized == "Greater Foobar Area"


def test_build_location_facets_groups_and_counts_normalized_values() -> None:
    facets = build_location_facets(
        [
            "Remote, US",
            "New York, NY",
            "New York, New York",
            "Austin TX",
            "Unknown",
            "",
        ]
    )

    assert {"group": REMOTE_GROUP, "value": "Remote", "count": 1} in facets["locations"]
    assert {"group": NORTHEAST_GROUP, "value": "New York, NY", "count": 2} in facets["locations"]
    assert {"group": SOUTH_GROUP, "value": "Austin, TX", "count": 1} in facets["locations"]
    assert {"group": NORTHEAST_GROUP, "count": 2} in facets["location_groups"]
