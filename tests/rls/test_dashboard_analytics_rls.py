"""Live RLS proof for the tenant-owned Dashboard analytics tables.

Set CAREERSIGNALS_RLS_TEST_DATABASE_URL to a disposable local Supabase database
(normally postgresql://postgres:postgres@127.0.0.1:54322/postgres). The guard
below refuses non-loopback targets.
"""

from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row


def _local_test_dsn() -> str:
    dsn = os.getenv("CAREERSIGNALS_RLS_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("CAREERSIGNALS_RLS_TEST_DATABASE_URL is not configured")
    parsed = urlparse(dsn)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("RLS integration tests only run against a loopback database")
    return dsn


def _insert_auth_user(connection, auth_user_id: str, email: str, username: str) -> None:
    connection.execute(
        """
        insert into auth.users (
            instance_id, id, aud, role, email, encrypted_password,
            email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
            created_at, updated_at, confirmation_token,
            email_change, email_change_token_new, recovery_token
        ) values (
            '00000000-0000-0000-0000-000000000000', %s::uuid,
            'authenticated', 'authenticated', %s, '', now(),
            '{}'::jsonb, %s::jsonb, now(), now(), '', '', '', ''
        )
        """,
        [auth_user_id, email, json.dumps({"username": username})],
    )


def test_user_cannot_select_another_users_metrics_or_status_events() -> None:
    dsn = _local_test_dsn()
    auth_a, auth_b = str(uuid4()), str(uuid4())
    job_a, job_b = f"rls-job-{uuid4()}", f"rls-job-{uuid4()}"

    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        try:
            _insert_auth_user(connection, auth_a, f"{auth_a}@example.test", f"rlsa{auth_a[:8]}")
            _insert_auth_user(connection, auth_b, f"{auth_b}@example.test", f"rlsb{auth_b[:8]}")
            profiles = connection.execute(
                """
                update public.user_profiles
                set account_status = 'active', activated_at = now(),
                    expires_at = now() + interval '30 days'
                where auth_user_id in (%s::uuid, %s::uuid)
                returning user_uuid, auth_user_id
                """,
                [auth_a, auth_b],
            ).fetchall()
            user_by_auth = {str(row["auth_user_id"]): str(row["user_uuid"]) for row in profiles}
            user_a, user_b = user_by_auth[auth_a], user_by_auth[auth_b]

            connection.execute(
                """
                insert into public.job_postings (
                    job_id, source_name, title, first_seen_at, last_seen_at, is_active
                ) values
                    (%s, 'rls_test', 'User A role', now(), now(), true),
                    (%s, 'rls_test', 'User B role', now(), now(), true)
                """,
                [job_a, job_b],
            )
            connection.execute(
                """
                insert into public.user_job_statuses (user_uuid, job_id, application_status)
                values (%s::uuid, %s, 'applied'), (%s::uuid, %s, 'interview')
                """,
                [user_a, job_a, user_b, job_b],
            )
            for next_status in ("interview", "rejected", "archived"):
                connection.execute(
                    """
                    update public.user_job_statuses
                    set application_status = %s
                    where user_uuid = %s::uuid and job_id = %s
                    """,
                    [next_status, user_a, job_a],
                )

            retained_funnel = connection.execute(
                """
                select applied_jobs_count, interview_jobs_count,
                       new_user_jobs_count, new_applied_jobs_count
                from public.user_job_daily_metrics
                where user_uuid = %s::uuid
                """,
                [user_a],
            ).fetchone()
            same_day_rows = connection.execute(
                """
                select count(*) as count
                from public.user_job_daily_metrics
                where user_uuid = %s::uuid
                """,
                [user_a],
            ).fetchone()
            assert retained_funnel == {
                "applied_jobs_count": 1,
                "interview_jobs_count": 1,
                "new_user_jobs_count": 0,
                "new_applied_jobs_count": 1,
            }
            assert same_day_rows == {"count": 1}

            connection.execute(
                "select set_config('request.jwt.claim.sub', %s, true)", [auth_a]
            )
            connection.execute(
                "select set_config('request.jwt.claim.role', 'authenticated', true)"
            )
            connection.execute("set local role authenticated")

            metric_owners = connection.execute(
                "select distinct user_uuid from public.user_job_daily_metrics"
            ).fetchall()
            event_owners = connection.execute(
                "select distinct user_uuid from public.user_job_status_events"
            ).fetchall()
            other_metrics = connection.execute(
                "select * from public.user_job_daily_metrics where user_uuid = %s::uuid",
                [user_b],
            ).fetchall()
            other_events = connection.execute(
                "select * from public.user_job_status_events where user_uuid = %s::uuid",
                [user_b],
            ).fetchall()

            assert {str(row["user_uuid"]) for row in metric_owners} == {user_a}
            assert {str(row["user_uuid"]) for row in event_owners} == {user_a}
            assert other_metrics == []
            assert other_events == []
        finally:
            connection.execute("reset role")
            connection.rollback()
