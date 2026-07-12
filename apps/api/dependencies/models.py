from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


class APIError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.headers = headers or {}


@dataclass(frozen=True)
class CurrentUser:
    user_uuid: UUID
    username: str
    role: str
    account_status: str
    created_at: datetime
    activated_at: datetime | None
    expires_at: datetime | None
    remaining_days: int | None
    last_successful_pipeline_run_uuid: UUID | None
    auth_user_id: UUID | None = None

    @property
    def is_demo(self) -> bool:
        return self.role == "demo"

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "CurrentUser":
        def as_uuid(value: Any) -> UUID | None:
            return UUID(str(value)) if value else None

        return cls(
            user_uuid=UUID(str(profile["user_uuid"])),
            username=str(profile["username"]),
            role=str(profile["role"]),
            account_status=str(profile["account_status"]),
            created_at=profile["created_at"],
            activated_at=profile.get("activated_at"),
            expires_at=profile.get("expires_at"),
            remaining_days=profile.get("remaining_days"),
            last_successful_pipeline_run_uuid=as_uuid(profile.get("last_successful_pipeline_run_uuid")),
            auth_user_id=as_uuid(profile.get("auth_user_id")),
        )
