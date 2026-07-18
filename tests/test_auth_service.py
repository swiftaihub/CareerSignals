from types import SimpleNamespace

import pytest
from supabase_auth.errors import AuthApiError

from apps.api.dependencies.models import APIError
from apps.api.services import auth_service
from apps.api.services.auth_service import AuthService


class _Users:
    def __init__(self, existing_identifiers: set[str] | None = None) -> None:
        self.existing_identifiers = existing_identifiers or set()

    def resolve_login_identifier(self, identifier: str):
        return {"user_uuid": "existing"} if identifier in self.existing_identifiers else None


class _Admin:
    def create_user(self, _payload):
        raise AssertionError("Supabase must not be called for a known duplicate")


class _Supabase:
    auth = SimpleNamespace(admin=_Admin())


class _RejectingAdmin:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def create_user(self, _payload):
        raise self.error


class _RejectingSupabase:
    def __init__(self, error: Exception) -> None:
        self.auth = SimpleNamespace(admin=_RejectingAdmin(error))


class _LoginUsers(_Users):
    def resolve_login_identifier(self, _identifier: str):
        return {
            "user_uuid": "00000000-0000-4000-8000-000000000001",
            "email": "available@example.com",
            "role": "user",
        }

    def touch_login(self, _user_uuid: str) -> None:
        return None


class _LoginAuth:
    def sign_in_with_password(self, _payload):
        return SimpleNamespace(
            session=SimpleNamespace(
                access_token="access",
                refresh_token="refresh",
                expires_in=3600,
                token_type="bearer",
            )
        )


@pytest.mark.parametrize("existing", [{"taken"}, {"taken@example.com"}])
def test_register_reports_known_username_or_email_conflict(existing: set[str]) -> None:
    service = AuthService(users=_Users(existing), supabase=_Supabase(), settings=object())

    with pytest.raises(APIError) as raised:
        service.register(
            username="taken",
            email="taken@example.com",
            password="long-enough-password",
        )

    assert raised.value.status_code == 409
    assert raised.value.error_code == "ACCOUNT_ALREADY_EXISTS"


@pytest.mark.parametrize(
    ("code", "expected_status", "expected_code"),
    [
        ("email_address_not_authorized", 422, "INVALID_EMAIL"),
        ("email_address_invalid", 422, "INVALID_EMAIL"),
        ("weak_password", 422, "WEAK_PASSWORD"),
        ("session_not_found", 503, "REGISTRATION_AUTH_UNAVAILABLE"),
        ("unexpected_policy_rejection", 422, "REGISTRATION_REJECTED"),
    ],
)
def test_register_preserves_actionable_supabase_rejections(
    code: str,
    expected_status: int,
    expected_code: str,
) -> None:
    error = AuthApiError("Supabase rejected the request", 403, code)  # type: ignore[arg-type]
    service = AuthService(users=_Users(), supabase=_RejectingSupabase(error), settings=object())

    with pytest.raises(APIError) as raised:
        service.register(
            username="available",
            email="available@example.com",
            password="long-enough-password",
        )

    assert raised.value.status_code == expected_status
    assert raised.value.error_code == expected_code


def test_login_uses_an_isolated_client_instead_of_mutating_cached_admin_client(monkeypatch) -> None:
    admin_client = SimpleNamespace(auth=SimpleNamespace(admin=object()))
    login_client = SimpleNamespace(auth=_LoginAuth())
    monkeypatch.setattr(auth_service, "get_supabase_admin_client", lambda: admin_client)
    monkeypatch.setattr(auth_service, "create_supabase_auth_client", lambda: login_client)

    service = AuthService(users=_LoginUsers(), settings=object())
    result = service.login("available", "long-enough-password")

    assert service.supabase is admin_client
    assert login_client is not admin_client
    assert result["access_token"] == "access"
