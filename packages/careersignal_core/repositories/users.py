"""PostgreSQL repository for tenant profiles."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from packages.careersignal_core.repositories.errors import ConflictError, NotFoundError
from packages.careersignal_core.storage.postgres import PostgresStore


PROFILE_SELECT = """
select
    p.user_uuid,
    p.auth_user_id,
    p.username::text as username,
    p.email::text as email,
    p.role::text as role,
    p.account_status::text as account_status,
    p.created_at,
    p.activated_at,
    p.expires_at,
    p.last_login_at,
    p.last_activity_at,
    p.last_successful_pipeline_run_uuid,
    p.pipeline_quota_reset_at,
    p.deleted_at,
    case
      when p.role in ('admin', 'demo') then null
      when p.expires_at is null then 0
      else greatest(0, ceil(extract(epoch from (p.expires_at - now())) / 86400.0))::integer
    end as remaining_days
from public.user_profiles p
"""


class UserRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def get_by_auth_user_id(self, auth_user_id: UUID | str) -> dict[str, Any] | None:
        return self.store.fetch_one(
            PROFILE_SELECT + " where p.auth_user_id = %s and p.deleted_at is null limit 1",
            [str(auth_user_id)],
        )

    def get_by_user_uuid(self, user_uuid: UUID | str, *, include_deleted: bool = False) -> dict[str, Any] | None:
        deleted_clause = "" if include_deleted else " and p.deleted_at is null"
        return self.store.fetch_one(
            PROFILE_SELECT + f" where p.user_uuid = %s{deleted_clause} limit 1",
            [str(user_uuid)],
        )

    def require_user(self, user_uuid: UUID | str) -> dict[str, Any]:
        profile = self.get_by_user_uuid(user_uuid)
        if profile is None:
            raise NotFoundError("User was not found")
        return profile

    def resolve_login_identifier(self, identifier: str) -> dict[str, Any] | None:
        """Resolve a username server-side without exposing this as a public lookup."""

        normalized = identifier.strip()
        return self.store.fetch_one(
            PROFILE_SELECT
            + " where p.deleted_at is null and (p.username = %s::citext or p.email = %s::citext) limit 1",
            [normalized, normalized],
        )

    def create_pending_profile(
        self,
        *,
        auth_user_id: UUID | str,
        username: str,
        email: str,
        role: str = "user",
    ) -> dict[str, Any]:
        try:
            with self.store.transaction() as connection:
                row = connection.execute(
                    """
                    insert into public.user_profiles (
                        auth_user_id, username, email, role, account_status
                    ) values (%s, %s, %s, %s::public.user_role, 'pending')
                    on conflict (auth_user_id) do update set
                        username = excluded.username,
                        email = excluded.email
                    returning user_uuid
                    """,
                    [str(auth_user_id), username.strip(), email.strip(), role],
                ).fetchone()
                user_uuid = row["user_uuid"]
                connection.execute(
                    """
                    insert into public.user_config_documents (user_uuid, config_type)
                    select %s, config_type
                    from unnest(enum_range(null::public.config_type)) as config_type
                    on conflict (user_uuid, config_type) do nothing
                    """,
                    [user_uuid],
                )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise ConflictError("Username or email is already registered") from exc
            raise
        return self.require_user(user_uuid)

    def touch_login(self, user_uuid: UUID | str) -> None:
        self.store.execute(
            """
            update public.user_profiles
            set last_login_at = now(), last_activity_at = now()
            where user_uuid = %s and deleted_at is null
            """,
            [str(user_uuid)],
        )

    def touch_activity(self, user_uuid: UUID | str) -> None:
        self.store.execute(
            """
            update public.user_profiles
            set last_activity_at = now()
            where user_uuid = %s and deleted_at is null
              and (last_activity_at is null or last_activity_at < now() - interval '5 minutes')
            """,
            [str(user_uuid)],
        )

    def update_safe_fields(self, user_uuid: UUID | str, *, username: str | None = None) -> dict[str, Any]:
        if username is None:
            return self.require_user(user_uuid)
        try:
            updated = self.store.fetch_one(
                """
                update public.user_profiles
                set username = %s, updated_at = now()
                where user_uuid = %s and deleted_at is null
                returning user_uuid
                """,
                [username.strip(), str(user_uuid)],
            )
        except Exception as exc:
            if getattr(exc, "sqlstate", None) == "23505":
                raise ConflictError("Username is already registered") from exc
            raise
        if updated is None:
            raise NotFoundError("User was not found")
        return self.require_user(user_uuid)
