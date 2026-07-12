"""Read models used exclusively by Admin endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from packages.careersignal_core.storage.postgres import PostgresStore


class AdminRepository:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def list_users(
        self,
        *,
        search: str | None,
        user_uuid: str | None,
        username: str | None,
        email: str | None,
        account_status: str | None,
        role: str | None,
        created_from: str | None,
        created_to: str | None,
        expires_from: str | None,
        expires_to: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if search:
            clauses.append("(username::text ilike %s or email::text ilike %s or user_uuid::text = %s)")
            value = f"%{search.strip()}%"
            params.extend([value, value, search.strip()])
        if user_uuid:
            clauses.append("user_uuid = %s")
            params.append(user_uuid)
        if username:
            clauses.append("username::text ilike %s")
            params.append(f"%{username.strip()}%")
        if email:
            clauses.append("email::text ilike %s")
            params.append(f"%{email.strip()}%")
        if account_status:
            clauses.append("account_status = %s::public.account_status")
            params.append(account_status)
        if role:
            clauses.append("role = %s::public.user_role")
            params.append(role)
        if created_from:
            clauses.append("created_at >= %s::date")
            params.append(created_from)
        if created_to:
            clauses.append("created_at < (%s::date + interval '1 day')")
            params.append(created_to)
        if expires_from:
            clauses.append("expires_at >= %s::date")
            params.append(expires_from)
        if expires_to:
            clauses.append("expires_at < (%s::date + interval '1 day')")
            params.append(expires_to)
        where_sql = " and ".join(clauses)
        count = self.store.fetch_one(
            f"select count(*) as count from public.user_profiles where {where_sql}", params
        )
        rows = self.store.fetch_all(
            f"""
            select user_uuid, username::text as username, email::text as email,
                   role::text as role, account_status::text as account_status,
                   created_at, activated_at, expires_at,
                   case when role in ('admin', 'demo') then null
                        when expires_at is null then 0
                        else greatest(0, ceil(extract(epoch from (expires_at - now())) / 86400.0))::int
                   end as remaining_days,
                   last_login_at, last_activity_at, last_successful_pipeline_run_uuid, deleted_at
            from public.user_profiles
            where {where_sql}
            order by created_at desc
            limit %s offset %s
            """,
            [*params, limit, offset],
        )
        return int((count or {}).get("count", 0)), rows

    def metrics(self, *, start_date: date, end_date: date, timezone: str = "UTC") -> dict[str, Any]:
        summary = self.store.fetch_one(
            """
            with users as (
              select * from public.user_profiles where deleted_at is null
            ), billing as (
              select
                coalesce(sum(case when status = 'succeeded' and event_type not in ('refund')
                                  then amount_cents else 0 end), 0) as gross,
                coalesce(sum(case when status = 'succeeded' and event_type = 'refund'
                                  then amount_cents else 0 end), 0) as refunds,
                coalesce(sum(case when status = 'succeeded' and event_type not in ('refund')
                                  and occurred_at >= date_trunc('month', now())
                                  then amount_cents else 0 end), 0) as month_revenue
              from public.billing_events
            ), pipelines as (
              select count(*) filter (where status in ('completed', 'failed')) as finished,
                     count(*) filter (where status = 'completed') as succeeded,
                     avg(extract(epoch from (completed_at - started_at)))
                       filter (where completed_at is not null and started_at is not null) as avg_seconds
              from public.user_pipeline_runs
              where submitted_at >= %s::date and submitted_at < (%s::date + interval '1 day')
            )
            select
              count(*) filter (where role <> 'demo') as total_registered_users,
              count(*) filter (where role <> 'demo' and created_at >= %s::date
                               and created_at < (%s::date + interval '1 day')) as new_registered_users,
              count(*) filter (where account_status = 'pending') as pending_users,
              count(*) filter (where account_status = 'active' and role <> 'demo') as active_users,
              count(*) filter (where account_status = 'expired') as expired_users,
              count(*) filter (where account_status = 'suspended') as suspended_users,
              count(*) filter (where account_status = 'active' and role = 'user') * 500
                as estimated_mrr_cents,
              billing.month_revenue as actual_monthly_revenue_cents,
              billing.gross - billing.refunds as total_revenue_cents,
              case when pipelines.finished = 0 then 0
                   else round(pipelines.succeeded::numeric / pipelines.finished, 4) end
                as pipeline_success_rate,
              coalesce(pipelines.avg_seconds, 0) as average_pipeline_duration_seconds
            from users cross join billing cross join pipelines
            group by billing.month_revenue, billing.gross, billing.refunds,
                     pipelines.finished, pipelines.succeeded, pipelines.avg_seconds
            """,
            [start_date, end_date, start_date, end_date],
        ) or {}
        summary.update(
            {
                "registrations_by_day": self.store.fetch_all(
                    """
                    select (created_at at time zone %s)::date as date, count(*) as value
                    from public.user_profiles
                    where role <> 'demo' and created_at >= %s::date
                      and created_at < (%s::date + interval '1 day')
                    group by 1 order by 1
                    """,
                    [timezone, start_date, end_date],
                ),
                "pipeline_runs_by_day": self.store.fetch_all(
                    """
                    select (submitted_at at time zone %s)::date as date,
                           count(*) as total,
                           count(*) filter (where status = 'failed') as failed
                    from public.user_pipeline_runs
                    where submitted_at >= %s::date and submitted_at < (%s::date + interval '1 day')
                    group by 1 order by 1
                    """,
                    [timezone, start_date, end_date],
                ),
                "activity_by_hour": self.store.fetch_all(
                    """
                    select extract(hour from event_time at time zone %s)::int as hour, count(*) as value
                    from public.user_activity_events
                    where event_time >= %s::date and event_time < (%s::date + interval '1 day')
                    group by 1 order by 1
                    """,
                    [timezone, start_date, end_date],
                ),
                "active_users_by_day": self.store.fetch_all(
                    """
                    select days.day::date as date, count(up.user_uuid) as value
                    from generate_series(%s::date, %s::date, interval '1 day') as days(day)
                    left join public.user_profiles up
                      on up.role = 'user'
                     and up.deleted_at is null
                     and up.account_status = 'active'
                     and up.created_at < (days.day + interval '1 day')
                     and (up.expires_at is null or up.expires_at >= days.day)
                    group by days.day order by days.day
                    """,
                    [start_date, end_date],
                ),
                "revenue_events_by_day": self.store.fetch_all(
                    """
                    select (occurred_at at time zone %s)::date as date,
                           coalesce(sum(amount_cents) filter (
                             where status = 'succeeded' and event_type <> 'refund'
                           ), 0) as value,
                           count(*) as count
                    from public.billing_events
                    where occurred_at >= %s::date and occurred_at < (%s::date + interval '1 day')
                    group by 1 order by 1
                    """,
                    [timezone, start_date, end_date],
                ),
                "expiration_outlook": self.store.fetch_all(
                    """
                    select expires_at::date as date, count(*) as value
                    from public.user_profiles
                    where role = 'user'
                      and deleted_at is null
                      and expires_at is not null
                      and expires_at >= %s::date
                      and expires_at < (%s::date + interval '1 day')
                    group by 1 order by 1
                    """,
                    [start_date, end_date],
                ),
            }
        )
        return summary
