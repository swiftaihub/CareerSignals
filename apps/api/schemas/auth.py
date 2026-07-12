from __future__ import annotations

import re

from pydantic import EmailStr, Field, field_validator

from apps.api.schemas.common import APIModel


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,31}$")


class LoginRequest(APIModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(APIModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=10, max_length=1024)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError("Username may contain letters, numbers, periods, underscores, and hyphens")
        return value


class DemoSessionResponse(APIModel):
    demo_token: str
    expires_at: str


class AuthSessionResponse(APIModel):
    access_token: str
    refresh_token: str
    expires_in: int | None = None
    token_type: str = "bearer"
