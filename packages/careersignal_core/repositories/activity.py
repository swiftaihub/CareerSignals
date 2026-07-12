"""Activity and immutable Admin audit logging."""

from __future__ import annotations

from datetime import date, datetime
import json
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.storage.postgres import PostgresStore


def _json_default(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default)


class ActivityRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def record_user_event(
        self,
        *,
        user_uuid: UUID | str | None,
        event_name: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.execute(
            """
            insert into public.user_activity_events (user_uuid, event_name, session_id, metadata)
            values (%s, %s, %s, %s::jsonb)
            """,
            [
                str(user_uuid) if user_uuid else None,
                event_name,
                session_id,
                Jsonb(metadata or {}, dumps=_json_dumps),
            ],
        )

    def record_admin_action(
        self,
        *,
        admin_user_uuid: UUID | str,
        target_user_uuid: UUID | str | None,
        action_name: str,
        before_state: dict[str, Any] | None,
        after_state: dict[str, Any] | None,
        request_id: str | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self.store.execute(
            """
            insert into public.admin_audit_logs (
                admin_user_uuid, target_user_uuid, action_name, before_state, after_state,
                request_id, ip_address, user_agent
            ) values (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::inet, %s)
            """,
            [
                str(admin_user_uuid),
                str(target_user_uuid) if target_user_uuid else None,
                action_name,
                Jsonb(before_state, dumps=_json_dumps) if before_state is not None else None,
                Jsonb(after_state, dumps=_json_dumps) if after_state is not None else None,
                request_id,
                ip_address,
                user_agent,
            ],
        )

    def list_audit_logs(
        self, *, limit: int, offset: int, action: str | None = None
    ) -> tuple[int, list[dict[str, Any]]]:
        where = "where l.action_name ilike %s" if action else ""
        params: list[Any] = [f"%{action}%"] if action else []
        total = self.store.fetch_one(
            f"select count(*) as count from public.admin_audit_logs l {where}", params
        )
        rows = self.store.fetch_all(
            f"""
            select l.*, a.username::text as admin_username, t.username::text as target_username
            from public.admin_audit_logs l
            join public.user_profiles a on a.user_uuid = l.admin_user_uuid
            left join public.user_profiles t on t.user_uuid = l.target_user_uuid
            {where}
            order by l.created_at desc
            limit %s offset %s
            """,
            [*params, limit, offset],
        )
        return int((total or {}).get("count", 0)), rows
