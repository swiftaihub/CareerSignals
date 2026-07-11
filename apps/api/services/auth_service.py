"""Server-only Supabase Auth orchestration."""

from __future__ import annotations

from functools import lru_cache
import logging
from typing import Any

from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

from apps.api.dependencies.models import APIError
from packages.careersignal_core.repositories.users import UserRepository
from packages.careersignal_core.settings import AppSettings, get_settings


LOGGER = logging.getLogger("careersignals.auth")


@lru_cache(maxsize=1)
def get_supabase_admin_client() -> Client:
    settings = get_settings()
    settings.require_backend_service_role()
    return create_client(settings.supabase_url, settings.supabase_service_role_key.get_secret_value())


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


class AuthService:
    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        supabase: Client | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.settings = settings or get_settings()
        self.supabase = supabase or get_supabase_admin_client()

    def login(self, identifier: str, password: str) -> dict[str, Any]:
        profile = self.users.resolve_login_identifier(identifier)
        # Keep username/email existence indistinguishable to callers.
        if profile is None or not profile.get("email") or profile.get("role") == "demo":
            raise APIError(401, "Invalid username/email or password.", "INVALID_CREDENTIALS")
        try:
            response = self.supabase.auth.sign_in_with_password(
                {"email": str(profile["email"]), "password": password}
            )
        except Exception as exc:
            raise APIError(401, "Invalid username/email or password.", "INVALID_CREDENTIALS") from exc
        session = _value(response, "session")
        if session is None:
            raise APIError(401, "Invalid username/email or password.", "INVALID_CREDENTIALS")
        self.users.touch_login(profile["user_uuid"])
        return {
            "access_token": _value(session, "access_token"),
            "refresh_token": _value(session, "refresh_token"),
            "expires_in": _value(session, "expires_in"),
            "token_type": _value(session, "token_type", "bearer"),
        }

    def register(self, *, username: str, email: str, password: str) -> dict[str, Any]:
        def account_exists() -> bool:
            return bool(
                self.users.resolve_login_identifier(username)
                or self.users.resolve_login_identifier(email)
            )

        # The auth.users trigger also creates the pending application profile.
        # A duplicate profile username is surfaced by GoTrue as the opaque
        # "Database error creating new user", so detect conflicts explicitly
        # and return the stable public error callers expect.
        if account_exists():
            raise APIError(409, "Username or email is already registered.", "ACCOUNT_ALREADY_EXISTS")

        auth_user_id: str | None = None
        try:
            response = self.supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"username": username, "requires_password_change": False},
                }
            )
            user = _value(response, "user", response)
            auth_user_id = str(_value(user, "id"))
            if not auth_user_id or auth_user_id == "None":
                raise RuntimeError("Supabase did not return an Auth user ID")
            return self.users.create_pending_profile(
                auth_user_id=auth_user_id,
                username=username,
                email=email,
            )
        except APIError:
            raise
        except Exception as exc:
            if auth_user_id:
                try:
                    self.supabase.auth.admin.delete_user(auth_user_id)
                except Exception:
                    pass
            message = str(exc).casefold()
            auth_code = str(getattr(exc, "code", "") or "").casefold()
            auth_status = getattr(exc, "status", None)
            LOGGER.warning(
                "registration_auth_failure status=%s code=%s type=%s message=%s",
                auth_status,
                auth_code or "unknown",
                type(exc).__name__,
                str(exc),
            )
            if (
                "already" in message
                or "unique" in message
                or "registered" in message
                or auth_code in {"email_exists", "user_already_exists"}
                or account_exists()
            ):
                raise APIError(409, "Username or email is already registered.", "ACCOUNT_ALREADY_EXISTS") from exc
            if auth_code == "weak_password" or "password" in auth_code:
                raise APIError(422, "Password does not meet the authentication policy.", "WEAK_PASSWORD") from exc
            if auth_code in {"email_address_invalid", "email_address_not_authorized"}:
                raise APIError(422, "This email address cannot be used for registration.", "INVALID_EMAIL") from exc
            if isinstance(exc, AuthApiError) and auth_status in {400, 403, 422}:
                raise APIError(422, "Supabase rejected the registration details.", "REGISTRATION_REJECTED") from exc
            raise APIError(503, "Registration is temporarily unavailable.", "REGISTRATION_UNAVAILABLE") from exc
