"""JSON snapshot persistence for pipeline runs."""

from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.utils.file_outputs import timestamped_output_path


def _json_default(value: Any) -> str | dict[str, Any]:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        if hasattr(value, "model_dump"):
            return value.model_dump()
        return value.dict()
    return str(value)


def write_json_snapshot(payload: dict[str, Any], base_path: str | Path) -> Path:
    """Write a timestamped JSON snapshot without replacing existing files."""

    output_path = timestamped_output_path(base_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False, default=_json_default)
        file.write("\n")
    return output_path
