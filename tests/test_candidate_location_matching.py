from pathlib import Path

import duckdb
from jinja2 import Environment


def _location_predicate() -> str:
    macro_path = Path("dbt/macros/candidate_location_matches.sql")
    macro = Environment().from_string(macro_path.read_text(encoding="utf-8")).module
    return macro.candidate_location_matches(
        "job_location",
        "job_location_normalized",
        "job_location_group",
        "job_work_arrangement",
        "configured_location",
    )


def _matches(
    configured_location: str,
    *,
    location: str,
    normalized: str,
    group: str = "Other or Unclassified",
    work_arrangement: str = "Unknown",
) -> bool:
    query = f"""
        select {_location_predicate()}
        from (
            select
                ?::varchar as configured_location,
                ?::varchar as job_location,
                ?::varchar as job_location_normalized,
                ?::varchar as job_location_group,
                ?::varchar as job_work_arrangement
        )
    """
    return bool(
        duckdb.connect(":memory:")
        .execute(query, [configured_location, location, normalized, group, work_arrangement])
        .fetchone()[0]
    )


def test_remote_location_matches_remote_work_arrangement() -> None:
    assert _matches(
        "Remote",
        location="Grand Central, Manhattan",
        normalized="Grand Central, Manhattan",
        work_arrangement="Remote",
    )


def test_city_state_location_matches_source_city_variants() -> None:
    assert _matches(
        "New York, NY",
        location="New York City, New York",
        normalized="New York City, NY",
        group="Northeast",
    )
    assert _matches(
        "Wilmington, DE",
        location="Wilmington, New Castle County",
        normalized="Wilmington, New Castle County",
    )
    assert _matches(
        "Philadelphia, PA",
        location="William Penn Annex East, Philadelphia County",
        normalized="William Penn Annex East, Philadelphia County",
    )


def test_unrelated_location_does_not_match() -> None:
    assert not _matches(
        "New York, NY",
        location="San Mateo, CA, United States",
        normalized="Multiple Locations",
        group="West",
        work_arrangement="On-site",
    )
