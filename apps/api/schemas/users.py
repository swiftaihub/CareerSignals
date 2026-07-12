from __future__ import annotations

from datetime import datetime
from uuid import UUID

from apps.api.schemas.common import APIModel


class CurrentUserResponse(APIModel):
    user_uuid: UUID
    username: str
    role: str
    account_status: str
    created_at: datetime
    activated_at: datetime | None = None
    expires_at: datetime | None = None
    remaining_days: int | None = None
    last_successful_pipeline_run_uuid: UUID | None = None
    is_demo: bool
