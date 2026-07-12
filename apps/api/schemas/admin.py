from __future__ import annotations

from pydantic import EmailStr, Field

from apps.api.schemas.auth import USERNAME_PATTERN
from apps.api.schemas.common import APIModel


class AdminCreateUserRequest(APIModel):
    username: str = Field(min_length=3, max_length=32, pattern=USERNAME_PATTERN.pattern)
    email: EmailStr
    temporary_password: str = Field(min_length=10, max_length=1024)
    require_password_change: bool = True


class AdminUpdateUserRequest(APIModel):
    username: str | None = Field(default=None, min_length=3, max_length=32, pattern=USERNAME_PATTERN.pattern)
    email: EmailStr | None = None


class EntitlementAdjustmentRequest(APIModel):
    days: int = Field(gt=0, le=3650)
    note: str | None = Field(default=None, max_length=1000)


class AdminNoteRequest(APIModel):
    note: str | None = Field(default=None, max_length=1000)
