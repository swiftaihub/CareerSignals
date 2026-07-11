"""Audited Admin account lifecycle operations."""

from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from fastapi import Request

from apps.api.dependencies.models import APIError, CurrentUser
from apps.api.services.auth_service import _value, get_supabase_admin_client
from packages.careersignal_core.repositories.activity import ActivityRepository
from packages.careersignal_core.repositories.entitlements import EntitlementRepository
from packages.careersignal_core.repositories.users import UserRepository
from packages.careersignal_core.storage.postgres import PostgresStore


class AdminService:
    def __init__(
        self,
        *,
        users: UserRepository | None = None,
        entitlements: EntitlementRepository | None = None,
        activity: ActivityRepository | None = None,
        store: PostgresStore | None = None,
        supabase: Any | None = None,
    ) -> None:
        self.users = users or UserRepository()
        self.entitlements = entitlements or EntitlementRepository()
        self.activity = activity or ActivityRepository()
        self.store = store or PostgresStore()
        self.supabase = supabase or get_supabase_admin_client()

    @staticmethod
    def _request_metadata(request: Request) -> tuple[str | None, str | None, str | None]:
        return (
            getattr(request.state, "request_id", None),
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
        )

    def _audit(
        self,
        *,
        admin: CurrentUser,
        target_user_uuid: UUID | str | None,
        action: str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        request: Request,
    ) -> None:
        request_id, ip_address, user_agent = self._request_metadata(request)
        self.activity.record_admin_action(
            admin_user_uuid=admin.user_uuid,
            target_user_uuid=target_user_uuid,
            action_name=action,
            before_state=before,
            after_state=after,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def create_user(
        self,
        *,
        admin: CurrentUser,
        username: str,
        email: str,
        temporary_password: str,
        require_password_change: bool,
        request: Request,
    ) -> dict[str, Any]:
        auth_user_id: str | None = None
        try:
            response = self.supabase.auth.admin.create_user(
                {
                    "email": email,
                    "password": temporary_password,
                    "email_confirm": True,
                    "user_metadata": {
                        "username": username,
                        "requires_password_change": require_password_change,
                    },
                }
            )
            auth_user_id = str(_value(_value(response, "user", response), "id"))
            profile = self.users.create_pending_profile(
                auth_user_id=auth_user_id, username=username, email=email
            )
        except Exception as exc:
            if auth_user_id:
                try:
                    self.supabase.auth.admin.delete_user(auth_user_id)
                except Exception:
                    pass
            if isinstance(exc, APIError):
                raise
            raise APIError(409, "The user could not be created.", "USER_CREATE_FAILED") from exc
        self._audit(
            admin=admin,
            target_user_uuid=profile["user_uuid"],
            action="user_created",
            before=None,
            after={k: v for k, v in profile.items() if k != "auth_user_id"},
            request=request,
        )
        return profile

    def update_user(
        self,
        *,
        admin: CurrentUser,
        target_user_uuid: UUID | str,
        username: str | None,
        email: str | None,
        request: Request,
    ) -> dict[str, Any]:
        before = self.users.require_user(target_user_uuid)
        if before["role"] == "demo" and email:
            raise APIError(409, "The Demo account cannot have an Auth email.", "PROTECTED_ACCOUNT")
        if email and before.get("auth_user_id"):
            self.supabase.auth.admin.update_user_by_id(
                str(before["auth_user_id"]), {"email": email}
            )
        with self.store.transaction() as connection:
            row = connection.execute(
                """
                update public.user_profiles
                set username = coalesce(%s, username), email = coalesce(%s, email)
                where user_uuid = %s
                returning user_uuid
                """,
                [username, email, str(target_user_uuid)],
            ).fetchone()
            if row is None:
                raise APIError(404, "User was not found.", "USER_NOT_FOUND")
        after = self.users.require_user(target_user_uuid)
        self._audit(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_profile_updated",
            before=before,
            after=after,
            request=request,
        )
        return after

    def _profile_mutation(
        self,
        *,
        admin: CurrentUser,
        target_user_uuid: UUID | str,
        action: str,
        mutation: Callable[[], Any],
        request: Request,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        before = (
            self.users.get_by_user_uuid(target_user_uuid, include_deleted=True)
            if include_deleted
            else self.users.require_user(target_user_uuid)
        )
        if before is None:
            raise APIError(404, "User was not found.", "USER_NOT_FOUND")
        mutation()
        after = self.users.require_user(target_user_uuid)
        self._audit(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action=action,
            before=before,
            after=after,
            request=request,
        )
        return after

    def activate(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, note: str | None, request: Request
    ) -> dict[str, Any]:
        return self._profile_mutation(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_activated",
            mutation=lambda: self.entitlements.activate(
                user_uuid=target_user_uuid,
                performed_by_user_uuid=admin.user_uuid,
                days=30,
                note=note,
            ),
            request=request,
            include_deleted=True,
        )

    def expire(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, note: str | None, request: Request
    ) -> dict[str, Any]:
        return self._profile_mutation(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_expired",
            mutation=lambda: self.entitlements.expire_now(
                user_uuid=target_user_uuid,
                performed_by_user_uuid=admin.user_uuid,
                note=note,
            ),
            request=request,
        )

    def adjust_days(
        self,
        *,
        admin: CurrentUser,
        target_user_uuid: UUID | str,
        days_delta: int,
        note: str | None,
        request: Request,
    ) -> dict[str, Any]:
        return self._profile_mutation(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="entitlement_days_adjusted",
            mutation=lambda: self.entitlements.adjust_days(
                user_uuid=target_user_uuid,
                days_delta=days_delta,
                performed_by_user_uuid=admin.user_uuid,
                note=note,
            ),
            request=request,
        )

    def _revoke_auth_sessions(self, auth_user_id: Any) -> None:
        if not auth_user_id:
            return
        admin_api = self.supabase.auth.admin
        if hasattr(admin_api, "_request"):
            admin_api._request(
                "POST",
                f"admin/users/{auth_user_id}/logout",
                no_resolve_json=True,
            )
            return
        revoke = getattr(admin_api, "revoke_sessions", None)
        if callable(revoke):
            revoke(str(auth_user_id))
            return
        raise APIError(502, "Auth session revocation is unavailable.", "AUTH_REVOKE_UNAVAILABLE")

    def suspend(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, request: Request
    ) -> dict[str, Any]:
        before = self.users.require_user(target_user_uuid)
        if before["role"] in {"admin", "demo"}:
            raise APIError(409, "This protected account cannot be suspended.", "PROTECTED_ACCOUNT")
        return self._profile_mutation(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_suspended",
            mutation=lambda: (
                self.store.execute(
                    "update public.user_profiles set account_status = 'suspended' where user_uuid = %s",
                    [str(target_user_uuid)],
                ),
                self._revoke_auth_sessions(before.get("auth_user_id")),
            ),
            request=request,
        )

    def restore(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, request: Request
    ) -> dict[str, Any]:
        return self._profile_mutation(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_restored",
            mutation=lambda: self.store.execute(
                """
                update public.user_profiles
                set deleted_at = null,
                    account_status = case
                      when role in ('admin', 'demo') then 'active'::public.account_status
                      when expires_at > now() then 'active'::public.account_status
                      when activated_at is null then 'pending'::public.account_status
                      else 'expired'::public.account_status
                    end
                where user_uuid = %s
                """,
                [str(target_user_uuid)],
            ),
            request=request,
        )

    def soft_delete(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, request: Request
    ) -> dict[str, Any]:
        before = self.users.require_user(target_user_uuid)
        if before["role"] in {"admin", "demo"}:
            raise APIError(409, "This protected account cannot be deleted.", "PROTECTED_ACCOUNT")
        self.store.execute(
            """
            update public.user_profiles
            set account_status = 'deleted', deleted_at = now()
            where user_uuid = %s
            """,
            [str(target_user_uuid)],
        )
        self._revoke_auth_sessions(before.get("auth_user_id"))
        after = self.users.get_by_user_uuid(target_user_uuid, include_deleted=True)
        self._audit(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="user_soft_deleted",
            before=before,
            after=after,
            request=request,
        )
        return after or {"user_uuid": str(target_user_uuid), "account_status": "deleted"}

    def reset_password(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, request: Request
    ) -> dict[str, str]:
        profile = self.users.require_user(target_user_uuid)
        if not profile.get("email") or profile["role"] == "demo":
            raise APIError(409, "This account has no password reset flow.", "PASSWORD_RESET_UNAVAILABLE")
        self.supabase.auth.reset_password_email(str(profile["email"]))
        self._audit(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="password_reset_requested",
            before=None,
            after=None,
            request=request,
        )
        return {"detail": "Password reset instructions were requested."}

    def revoke_sessions(
        self, *, admin: CurrentUser, target_user_uuid: UUID | str, request: Request
    ) -> dict[str, str]:
        profile = self.users.require_user(target_user_uuid)
        self._revoke_auth_sessions(profile.get("auth_user_id"))
        self._audit(
            admin=admin,
            target_user_uuid=target_user_uuid,
            action="sessions_revoked",
            before=None,
            after=None,
            request=request,
        )
        return {"detail": "User sessions were revoked."}
