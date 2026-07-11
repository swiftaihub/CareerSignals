from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from apps.api.schemas.common import APIModel


class PipelineRunSubmission(APIModel):
    run_uuid: UUID
    status: str
    submitted_at: datetime
    config_hash: str


class PipelineRunEvent(APIModel):
    event_uuid: UUID
    event_level: str
    event_type: str
    message: str
    created_at: datetime


class PipelineRunResponse(APIModel):
    run_uuid: UUID
    status: str
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    published_at: datetime | None = None
    jobs_considered: int = 0
    jobs_matched: int = 0
    error_code: str | None = None
    public_error_message: str | None = None
    events: list[PipelineRunEvent] = []
