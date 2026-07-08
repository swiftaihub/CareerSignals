"""Helpers for safe, non-overwriting output file paths."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


def timestamped_output_path(
    base_path: str | Path,
    timestamp: datetime | None = None,
) -> Path:
    """Return a timestamped output path derived from a configured base path.

    Example:
        outputs/job_search_tracker.xlsx -> outputs/job_search_tracker_20260708_143012.xlsx

    If the generated filename already exists, a numeric suffix is added to avoid
    replacing an existing output.
    """

    path = Path(base_path)
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.stem}_{stamp}{path.suffix}")

    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}_{stamp}_{counter}{path.suffix}")
        counter += 1

    return candidate
