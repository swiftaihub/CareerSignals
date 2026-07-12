from __future__ import annotations

from typing import Any

from pydantic import Field

from apps.api.schemas.common import APIModel


class ConfigUpdateRequest(APIModel):
    override_config: dict[str, Any]


class ResetFieldRequest(APIModel):
    field_path: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_.-]+$")
