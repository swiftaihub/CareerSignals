"""Transactional account entitlement mutations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from packages.careersignal_core.repositories.errors import InvalidStateTransitionError, NotFoundError
from packages.careersignal_core.storage.postgres import PostgresStore


class EntitlementRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def activate(
        self,
        *,
        user_uuid: UUID | str,
        performed_by_user_uuid: UUID | str,
        days: int = 30,
        note: str | None = None,
    ) -> dict[str, Any]:
        if days <= 0:
            raise ValueError("Activation days must be positive")
        with self.store.transaction() as connection:
            profile = connection.execute(
                "select * from public.user_profiles where user_uuid = %s for update",
                [str(user_uuid)],
            ).fetchone()
            if profile is None:
                raise NotFoundError("User was not found")
            if profile["role"] == "demo":
                raise InvalidStateTransitionError("Demo entitlement cannot be changed")
            if profile["role"] != "admin" and profile["account_status"] != "pending":
                raise InvalidStateTransitionError("Only a pending account may be activated")
            previous = profile["expires_at"]
            row = connection.execute(
                """
                update public.user_profiles
                set account_status = 'active',
                    activated_at = coalesce(activated_at, now()),
                    expires_at = case
                      when role = 'admin' then null
                      else now() + (%s * interval '1 day')
                    end,
                    deleted_at = null
                where user_uuid = %s
                returning expires_at
                """,
                [days, str(user_uuid)],
            ).fetchone()
            connection.execute(
                """
                insert into public.entitlement_events (
                    user_uuid, event_type, days_delta, previous_expires_at, new_expires_at,
                    performed_by_user_uuid, note
                ) values (%s, 'initial_activation', %s, %s, %s, %s, %s)
                """,
                [str(user_uuid), days, previous, row["expires_at"], str(performed_by_user_uuid), note],
            )
        return {"user_uuid": str(user_uuid), "account_status": "active", "expires_at": row["expires_at"]}

    def adjust_days(
        self,
        *,
        user_uuid: UUID | str,
        days_delta: int,
        performed_by_user_uuid: UUID | str,
        note: str | None = None,
    ) -> dict[str, Any]:
        if days_delta == 0:
            raise ValueError("days_delta must not be zero")
        event_type = "admin_grant" if days_delta > 0 else "admin_reduction"
        with self.store.transaction() as connection:
            profile = connection.execute(
                "select * from public.user_profiles where user_uuid = %s for update",
                [str(user_uuid)],
            ).fetchone()
            if profile is None:
                raise NotFoundError("User was not found")
            if profile["role"] in {"admin", "demo"}:
                raise InvalidStateTransitionError("This account does not have an expiring entitlement")
            previous = profile["expires_at"]
            if days_delta > 0:
                updated = connection.execute(
                    """
                    update public.user_profiles
                    set expires_at = greatest(now(), coalesce(expires_at, now())) + (%s * interval '1 day'),
                        account_status = case when account_status = 'expired' then 'active' else account_status end
                    where user_uuid = %s
                    returning expires_at, account_status::text as account_status
                    """,
                    [days_delta, str(user_uuid)],
                ).fetchone()
            else:
                updated = connection.execute(
                    """
                    update public.user_profiles
                    set expires_at = greatest(now(), coalesce(expires_at, now()) + (%s * interval '1 day')),
                        account_status = case
                          when coalesce(expires_at, now()) + (%s * interval '1 day') <= now() then 'expired'
                          else account_status
                        end
                    where user_uuid = %s
                    returning expires_at, account_status::text as account_status
                    """,
                    [days_delta, days_delta, str(user_uuid)],
                ).fetchone()
            connection.execute(
                """
                insert into public.entitlement_events (
                    user_uuid, event_type, days_delta, previous_expires_at, new_expires_at,
                    performed_by_user_uuid, note
                ) values (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    str(user_uuid), event_type, days_delta, previous, updated["expires_at"],
                    str(performed_by_user_uuid), note,
                ],
            )
        return dict(updated)

    def expire_now(
        self, *, user_uuid: UUID | str, performed_by_user_uuid: UUID | str, note: str | None = None
    ) -> dict[str, Any]:
        with self.store.transaction() as connection:
            profile = connection.execute(
                "select role::text as role, expires_at from public.user_profiles where user_uuid = %s for update",
                [str(user_uuid)],
            ).fetchone()
            if profile is None:
                raise NotFoundError("User was not found")
            if profile["role"] in {"admin", "demo"}:
                raise InvalidStateTransitionError("This account cannot be expired")
            updated = connection.execute(
                """
                update public.user_profiles
                set account_status = 'expired', expires_at = now()
                where user_uuid = %s returning expires_at
                """,
                [str(user_uuid)],
            ).fetchone()
            connection.execute(
                """
                insert into public.entitlement_events (
                  user_uuid, event_type, days_delta, previous_expires_at, new_expires_at,
                  performed_by_user_uuid, note
                ) values (%s, 'expiration', 0, %s, %s, %s, %s)
                """,
                [str(user_uuid), profile["expires_at"], updated["expires_at"], str(performed_by_user_uuid), note],
            )
        return {"account_status": "expired", "expires_at": updated["expires_at"]}
