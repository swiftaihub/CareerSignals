from __future__ import annotations

from pydantic import Field

from apps.api.schemas.common import APIModel


class JobStatusUpdate(APIModel):
    application_status: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=4000)
