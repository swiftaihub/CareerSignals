from types import SimpleNamespace

import pytest
from supabase_auth.errors import AuthApiError

from apps.api.dependencies.models import APIError
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
    ("code", "expected_code"),
    [
        ("email_address_not_authorized", "INVALID_EMAIL"),
        ("email_address_invalid", "INVALID_EMAIL"),
        ("weak_password", "WEAK_PASSWORD"),
        ("unexpected_policy_rejection", "REGISTRATION_REJECTED"),
    ],
)
def test_register_preserves_actionable_supabase_rejections(code: str, expected_code: str) -> None:
    error = AuthApiError("Supabase rejected the request", 403, code)  # type: ignore[arg-type]
    service = AuthService(users=_Users(), supabase=_RejectingSupabase(error), settings=object())

    with pytest.raises(APIError) as raised:
        service.register(
            username="available",
            email="available@example.com",
            password="long-enough-password",
        )

    assert raised.value.status_code == 422
    assert raised.value.error_code == expected_code
