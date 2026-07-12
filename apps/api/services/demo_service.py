from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt

from apps.api.dependencies.models import APIError
from packages.careersignal_core.settings import AppSettings, SettingsError, get_settings


DEMO_ISSUER = "careersignals-demo"
DEMO_AUDIENCE = "careersignals-api"


def create_demo_session(settings: AppSettings | None = None) -> tuple[str, datetime]:
    config = settings or get_settings()
    secret = config.demo_session_secret.get_secret_value()
    if not secret or not config.demo_user_uuid:
        raise SettingsError("DEMO_USER_UUID and DEMO_SESSION_SECRET are required")
    if len(secret.encode("utf-8")) < 32:
        raise SettingsError("DEMO_SESSION_SECRET must be at least 32 bytes")
    try:
        subject = str(UUID(config.demo_user_uuid))
    except ValueError as exc:
        raise SettingsError("DEMO_USER_UUID must be a valid UUID") from exc
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=config.demo_session_ttl_minutes)
    token = jwt.encode(
        {
            "sub": subject,
            "role": "demo",
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": DEMO_ISSUER,
            "aud": DEMO_AUDIENCE,
            "jti": f"demo-{int(now.timestamp() * 1_000_000)}",
        },
        secret,
        algorithm="HS256",
    )
    return token, expires_at


def verify_demo_session(token: str, *, settings: AppSettings | None = None) -> dict[str, Any]:
    config = settings or get_settings()
    secret = config.demo_session_secret.get_secret_value()
    if not secret:
        raise APIError(401, "The Demo session is invalid.", "INVALID_DEMO_SESSION")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=DEMO_ISSUER,
            audience=DEMO_AUDIENCE,
            options={"require": ["exp", "sub", "role"]},
            leeway=10,
        )
    except Exception as exc:
        raise APIError(401, "The Demo session is invalid or expired.", "INVALID_DEMO_SESSION") from exc
    if claims.get("role") != "demo" or str(claims.get("sub")) != config.demo_user_uuid:
        raise APIError(401, "The Demo session is invalid.", "INVALID_DEMO_SESSION")
    return claims
