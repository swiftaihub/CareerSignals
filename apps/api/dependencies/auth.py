"""Supabase JWT verification and fixed signed Demo identity resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, Header
from jwt import PyJWKClient

from apps.api.dependencies.models import APIError, CurrentUser
from apps.api.services.demo_service import verify_demo_session
from packages.careersignal_core.repositories.users import UserRepository
from packages.careersignal_core.settings import AppSettings, get_settings, saas_mode


LOCAL_USER_UUID = UUID("00000000-0000-0000-0000-000000000001")


@lru_cache(maxsize=4)
def _jwk_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_keys=True, lifespan=300)


def _verify_supabase_token(token: str, settings: AppSettings) -> dict[str, object]:
    try:
        signing_key = _jwk_client(settings.jwks_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "aud"]},
            leeway=30,
        )
    except Exception as exc:
        raise APIError(
            401,
            "Your session is invalid or has expired.",
            "INVALID_ACCESS_TOKEN",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _local_identity() -> CurrentUser:
    now = datetime.now(timezone.utc)
    return CurrentUser(
        user_uuid=LOCAL_USER_UUID,
        username="local-user",
        role="user",
        account_status="active",
        created_at=now,
        activated_at=now,
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )


def get_current_identity(
    authorization: str | None = Header(default=None, alias="Authorization"),
    settings: AppSettings = Depends(get_settings),
) -> CurrentUser:
    if not saas_mode():
        return _local_identity()
    if not authorization:
        raise APIError(
            401,
            "Authentication is required.",
            "AUTHENTICATION_REQUIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, token = authorization.strip().partition(" ")
    if not scheme or not token:
        raise APIError(401, "Unsupported authentication scheme.", "AUTHENTICATION_REQUIRED")

    if scheme.casefold() == "demo":
        claims = verify_demo_session(token.strip(), settings=settings)
        profile = UserRepository().get_by_user_uuid(str(claims["sub"]))
        if profile is None or profile.get("role") != "demo":
            raise APIError(401, "The Demo session is invalid.", "INVALID_DEMO_SESSION")
        return CurrentUser.from_profile(profile)

    if scheme.casefold() != "bearer":
        raise APIError(401, "Unsupported authentication scheme.", "AUTHENTICATION_REQUIRED")
    claims = _verify_supabase_token(token.strip(), settings)
    subject = claims.get("sub")
    try:
        auth_user_id = UUID(str(subject))
    except (TypeError, ValueError) as exc:
        raise APIError(401, "Your session is invalid.", "INVALID_ACCESS_TOKEN") from exc
    profile = UserRepository().get_by_auth_user_id(auth_user_id)
    if profile is None:
        raise APIError(403, "Your CareerSignals profile is unavailable.", "PROFILE_NOT_FOUND")
    return CurrentUser.from_profile(profile)


def require_authenticated_user(
    current_user: CurrentUser = Depends(get_current_identity),
) -> CurrentUser:
    return current_user
