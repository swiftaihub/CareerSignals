"""Idempotently bootstrap the first Supabase Auth + CareerSignals Admin profile."""

from __future__ import annotations

from typing import Any

from apps.api.services.auth_service import _value, get_supabase_admin_client
from packages.careersignal_core.repositories.users import UserRepository
from packages.careersignal_core.settings import get_settings
from packages.careersignal_core.storage.postgres import PostgresStore


def _find_auth_user_by_email(client: Any, email: str) -> Any | None:
    page = 1
    while page <= 100:
        response = client.auth.admin.list_users(page=page, per_page=100)
        users = _value(response, "users", response) or []
        for user in users:
            if str(_value(user, "email", "")).casefold() == email.casefold():
                return user
        if len(users) < 100:
            return None
        page += 1
    return None


def bootstrap_admin() -> dict[str, object]:
    settings = get_settings()
    settings.require_api_configuration()
    settings.require_backend_service_role()
    email = settings.admin_bootstrap_email.strip()
    password = settings.admin_bootstrap_password.get_secret_value()
    if not email or not password:
        raise RuntimeError("ADMIN_BOOTSTRAP_EMAIL and ADMIN_BOOTSTRAP_PASSWORD are required")

    client = get_supabase_admin_client()
    auth_user = _find_auth_user_by_email(client, email)
    if auth_user is None:
        response = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"username": settings.admin_bootstrap_username},
            }
        )
        auth_user = _value(response, "user", response)
    auth_user_id = str(_value(auth_user, "id"))

    store = PostgresStore()
    with store.transaction() as connection:
        row = connection.execute(
            """
            insert into public.user_profiles (
              auth_user_id, username, email, role, account_status, activated_at, expires_at
            ) values (%s, %s, %s, 'admin', 'active', now(), null)
            on conflict (auth_user_id) do update set
              username = excluded.username,
              email = excluded.email,
              role = 'admin',
              account_status = 'active',
              activated_at = coalesce(user_profiles.activated_at, now()),
              expires_at = null,
              deleted_at = null
            returning user_uuid, username::text as username, email::text as email,
                      role::text as role, account_status::text as account_status
            """,
            [auth_user_id, settings.admin_bootstrap_username, email],
        ).fetchone()
        connection.execute(
            """
            insert into public.user_config_documents (user_uuid, config_type)
            select %s, config_type from unnest(enum_range(null::public.config_type)) config_type
            on conflict (user_uuid, config_type) do nothing
            """,
            [row["user_uuid"]],
        )
    return dict(row)


def main() -> None:
    profile = bootstrap_admin()
    print(f"Admin profile ready: {profile['username']} ({profile['user_uuid']})")


if __name__ == "__main__":
    main()
