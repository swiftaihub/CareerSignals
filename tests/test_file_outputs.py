from __future__ import annotations

from datetime import datetime

from src.utils.file_outputs import timestamped_output_path


def test_timestamped_output_path_appends_timestamp_before_suffix(tmp_path) -> None:
    path = timestamped_output_path(
        tmp_path / "job_search_tracker.xlsx",
        timestamp=datetime(2026, 7, 8, 14, 30, 12),
    )

    assert path.name == "job_search_tracker_20260708_143012.xlsx"


def test_timestamped_output_path_avoids_existing_file(tmp_path) -> None:
    existing = tmp_path / "job_search_tracker_20260708_143012.xlsx"
    existing.touch()

    path = timestamped_output_path(
        tmp_path / "job_search_tracker.xlsx",
        timestamp=datetime(2026, 7, 8, 14, 30, 12),
    )

    assert path.name == "job_search_tracker_20260708_143012_2.xlsx"
