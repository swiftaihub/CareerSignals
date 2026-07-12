from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apps.api.routers.exports import build_export_filename


def test_export_filename_is_public_dated_and_collision_safe() -> None:
    filename = build_export_filename(
        now=datetime(2026, 7, 11, 12, 30, tzinfo=ZoneInfo("America/New_York")),
        unique_suffix="A1-b2_c3",
    )

    assert filename == "CareerSignals_Matches_2026-07-11_A1b2c3.xlsx"
    assert "user" not in filename.casefold()
    assert "uuid" not in filename.casefold()


def test_export_filename_generates_a_unique_suffix() -> None:
    now = datetime(2026, 7, 11, tzinfo=ZoneInfo("UTC"))

    first = build_export_filename(now=now)
    second = build_export_filename(now=now)

    assert first.startswith("CareerSignals_Matches_2026-07-11_")
    assert first.endswith(".xlsx")
    assert first != second
