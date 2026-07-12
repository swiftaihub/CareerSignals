from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pytest
from starlette.requests import Request

from apps.api.dependencies.authorization import require_active_user
from apps.api.dependencies import auth as auth_dependencies
from apps.api.dependencies.models import APIError, CurrentUser
from apps.api.services.admin_service import AdminService
from apps.api.services.demo_service import create_demo_session
from packages.careersignal_core.settings import AppSettings


def _user(*, role: str = "user", account_status: str = "active") -> CurrentUser:
    return CurrentUser(
        user_uuid=UUID("11111111-1111-4111-8111-111111111111"),
        username="security-test",
        role=role,
        account_status=account_status,
        created_at=datetime(2026, 7, 1),
        activated_at=datetime(2026, 7, 1),
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )


def test_suspended_admin_cannot_bypass_active_account_check() -> None:
    with pytest.raises(APIError) as raised:
        require_active_user(_user(role="admin", account_status="suspended"))

    assert raised.value.status_code == 403
    assert raised.value.error_code == "ACCOUNT_SUSPENDED"


def test_active_demo_and_admin_accounts_are_allowed() -> None:
    assert require_active_user(_user(role="admin")).role == "admin"
    assert require_active_user(_user(role="demo")).role == "demo"


def test_admin_session_revoke_uses_admin_user_logout_endpoint() -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class FakeAdminAPI:
        def _request(self, *args: object, **kwargs: object) -> None:
            calls.append((args, kwargs))

        def sign_out(self, *_: object, **__: object) -> None:
            raise AssertionError("sign_out expects a JWT and must not receive a user UUID")

    class FakeAuth:
        admin = FakeAdminAPI()

    class FakeSupabase:
        auth = FakeAuth()

    service = AdminService(
        users=object(),
        entitlements=object(),
        activity=object(),
        store=object(),
        supabase=FakeSupabase(),
    )

    service._revoke_auth_sessions("22222222-2222-4222-8222-222222222222")

    assert calls == [
        (
            ("POST", "admin/users/22222222-2222-4222-8222-222222222222/logout"),
            {"no_resolve_json": True},
        )
    ]


def test_demo_authorization_scheme_resolves_demo_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_USER_UUID", "00000000-0000-4000-8000-000000000020")
    monkeypatch.setenv("DEMO_SESSION_SECRET", "x" * 64)
    settings = AppSettings()
    token, _ = create_demo_session(settings)

    class FakeUserRepository:
        def get_by_user_uuid(self, user_uuid: str) -> dict[str, object] | None:
            assert user_uuid == "00000000-0000-4000-8000-000000000020"
            return {
                "user_uuid": user_uuid,
                "username": "demo",
                "role": "demo",
                "account_status": "active",
                "created_at": datetime(2026, 7, 1),
                "activated_at": datetime(2026, 7, 1),
                "expires_at": None,
                "remaining_days": None,
                "last_successful_pipeline_run_uuid": None,
                "auth_user_id": None,
            }

    monkeypatch.setattr(auth_dependencies, "saas_mode", lambda: True)
    monkeypatch.setattr(auth_dependencies, "UserRepository", FakeUserRepository)

    identity = auth_dependencies.get_current_identity(
        authorization=f"Demo {token}",
        settings=settings,
    )

    assert identity.user_uuid == UUID("00000000-0000-4000-8000-000000000020")
    assert identity.role == "demo"


def test_admin_pipeline_quota_refresh_preserves_history_and_is_audited() -> None:
    profile = {
        "user_uuid": "22222222-2222-4222-8222-222222222222",
        "username": "quota-user",
        "role": "user",
        "pipeline_quota_reset_at": None,
    }
    actions: list[dict[str, object]] = []

    class FakeUsers:
        def require_user(self, user_uuid: object) -> dict[str, object]:
            assert str(user_uuid) == profile["user_uuid"]
            return dict(profile)

    class FakeStore:
        def execute(self, statement: str, params: list[str]) -> int:
            assert "set pipeline_quota_reset_at = now()" in " ".join(statement.split())
            assert params == [profile["user_uuid"]]
            profile["pipeline_quota_reset_at"] = "2026-07-12T12:00:00Z"
            return 1

    class FakeActivity:
        def record_admin_action(self, **kwargs: object) -> None:
            actions.append(kwargs)

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/admin/users/quota/refresh-pipeline-quota",
            "headers": [],
            "client": ("127.0.0.1", 1234),
        }
    )
    service = AdminService(
        users=FakeUsers(),
        entitlements=object(),
        activity=FakeActivity(),
        store=FakeStore(),
        supabase=object(),
    )

    result = service.refresh_pipeline_quota(
        admin=_user(role="admin"),
        target_user_uuid=profile["user_uuid"],
        request=request,
    )

    assert result == {"detail": "The user's daily pipeline allowance was refreshed."}
    assert actions[0]["action_name"] == "pipeline_quota_refreshed"
    assert actions[0]["before_state"]["pipeline_quota_reset_at"] is None
    assert actions[0]["after_state"]["pipeline_quota_reset_at"] is not None
