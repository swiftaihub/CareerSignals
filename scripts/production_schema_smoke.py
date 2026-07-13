"""Validate required production tables and the reviewed RLS metadata contract.

This command is intended for the manual migration workflow. It reports only
schema object names and exception classes; it never prints connection details.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

import psycopg


EXPECTED_RLS_TABLES = frozenset(
    {
        "admin_audit_logs",
        "billing_events",
        "config_bundle_revisions",
        "connector_acquisition_queries",
        "connector_refresh_runs",
        "connector_run_user_config_snapshots",
        "connector_source_runs",
        "entitlement_events",
        "global_job_daily_metrics",
        "job_postings",
        "skill_alias_catalog",
        "user_activity_events",
        "user_bootstrap_workflows",
        "user_category_summary",
        "user_company_priority",
        "user_config_documents",
        "user_config_versions",
        "user_job_daily_metrics",
        "user_job_matches",
        "user_job_status_events",
        "user_job_statuses",
        "user_pipeline_run_events",
        "user_pipeline_runs",
        "user_profiles",
        "user_skill_gap",
    }
)

EXPECTED_RLS_POLICY_TARGETS = {
    "admin_audit_logs_admin_select": ("admin_audit_logs", "SELECT"),
    "billing_events_admin_select": ("billing_events", "SELECT"),
    "config_bundle_revisions_self_or_admin_select": ("config_bundle_revisions", "SELECT"),
    "connector_acquisition_queries_admin_select": ("connector_acquisition_queries", "SELECT"),
    "connector_refresh_runs_admin_select": ("connector_refresh_runs", "SELECT"),
    "connector_run_user_snapshots_admin_select": ("connector_run_user_config_snapshots", "SELECT"),
    "connector_source_runs_admin_select": ("connector_source_runs", "SELECT"),
    "entitlement_events_self_or_admin_select": ("entitlement_events", "SELECT"),
    "global_job_daily_metrics_active_or_admin_select": ("global_job_daily_metrics", "SELECT"),
    "job_postings_current_match_or_admin_select": ("job_postings", "SELECT"),
    "skill_alias_catalog_admin_select": ("skill_alias_catalog", "SELECT"),
    "user_activity_events_self_or_admin_select": ("user_activity_events", "SELECT"),
    "user_bootstrap_workflows_self_or_admin_select": ("user_bootstrap_workflows", "SELECT"),
    "user_category_summary_self_or_admin_select": ("user_category_summary", "SELECT"),
    "user_company_priority_self_or_admin_select": ("user_company_priority", "SELECT"),
    "user_config_documents_self_or_admin_insert": ("user_config_documents", "INSERT"),
    "user_config_documents_self_or_admin_select": ("user_config_documents", "SELECT"),
    "user_config_documents_self_or_admin_update": ("user_config_documents", "UPDATE"),
    "user_config_versions_self_or_admin_select": ("user_config_versions", "SELECT"),
    "user_job_daily_metrics_self_or_admin_select": ("user_job_daily_metrics", "SELECT"),
    "user_job_matches_self_or_admin_select": ("user_job_matches", "SELECT"),
    "user_job_status_events_self_or_admin_select": ("user_job_status_events", "SELECT"),
    "user_job_statuses_self_or_admin_insert": ("user_job_statuses", "INSERT"),
    "user_job_statuses_self_or_admin_select": ("user_job_statuses", "SELECT"),
    "user_job_statuses_self_or_admin_update": ("user_job_statuses", "UPDATE"),
    "user_pipeline_run_events_self_or_admin_select": ("user_pipeline_run_events", "SELECT"),
    "user_pipeline_runs_self_or_admin_select": ("user_pipeline_runs", "SELECT"),
    "user_profiles_admin_update": ("user_profiles", "UPDATE"),
    "user_profiles_self_or_admin_select": ("user_profiles", "SELECT"),
    "user_skill_gap_self_or_admin_select": ("user_skill_gap", "SELECT"),
}
EXPECTED_RLS_POLICIES = frozenset(EXPECTED_RLS_POLICY_TARGETS)


def validate_rls_rows(rows: Iterable[tuple[str, bool, bool]]) -> None:
    """Raise a fixed, non-secret error for missing or unprotected tables."""

    observed = {name: (enabled, forced) for name, enabled, forced in rows}
    missing = sorted(EXPECTED_RLS_TABLES - observed.keys())
    unsafe = sorted(
        name
        for name, (enabled, forced) in observed.items()
        if name in EXPECTED_RLS_TABLES and (not enabled or not forced)
    )
    if missing:
        raise RuntimeError("Missing required public tables: " + ", ".join(missing))
    if unsafe:
        raise RuntimeError("RLS is not enabled and forced for: " + ", ".join(unsafe))


def validate_policy_names(names: Iterable[str]) -> None:
    """Require the live public policy inventory to match the reviewed set."""

    observed = set(names)
    missing = sorted(EXPECTED_RLS_POLICIES - observed)
    unexpected = sorted(observed - EXPECTED_RLS_POLICIES)
    if missing:
        raise RuntimeError("Missing required RLS policies: " + ", ".join(missing))
    if unexpected:
        raise RuntimeError("Unexpected public RLS policies: " + ", ".join(unexpected))


def validate_policy_rows(
    rows: Iterable[tuple[str, str, str, list[str], str, str | None, str | None]],
) -> None:
    """Validate target, role, command, and minimum expression invariants."""

    observed_rows = list(rows)
    validate_policy_names(row[1] for row in observed_rows)
    unsafe: list[str] = []
    for table, name, permissive, roles, command, using, with_check in observed_rows:
        expected_table, expected_command = EXPECTED_RLS_POLICY_TARGETS[name]
        expressions = " ".join(part or "" for part in (using, with_check)).casefold()
        if (
            table != expected_table
            or permissive != "PERMISSIVE"
            or roles != ["authenticated"]
            or command != expected_command
            or "is_current_user_admin()" not in expressions
            or re.search(r"\btrue\b", expressions)
        ):
            unsafe.append(name)
            continue
        if "self_or_admin" in name or "current_match_or_admin" in name:
            if "current_app_user_uuid()" not in expressions:
                unsafe.append(name)
                continue
        if "active_or_admin" in name or "current_match_or_admin" in name:
            if "is_current_user_active()" not in expressions:
                unsafe.append(name)
                continue
        if command == "SELECT" and (not using or with_check):
            unsafe.append(name)
        elif command == "INSERT" and (using or not with_check):
            unsafe.append(name)
        elif command == "UPDATE" and (not using or not with_check):
            unsafe.append(name)
        if command in {"INSERT", "UPDATE"} and name != "user_profiles_admin_update":
            if "current_app_role()" not in expressions or "demo" not in expressions:
                unsafe.append(name)
    if unsafe:
        raise RuntimeError("RLS policy metadata differs from the reviewed contract: " + ", ".join(sorted(set(unsafe))))


def main() -> int:
    database_url = os.getenv("SUPABASE_DB_DIRECT_URL", "").strip()
    if not database_url:
        print("Production schema smoke failed: SUPABASE_DB_DIRECT_URL is missing.")
        return 2

    try:
        with psycopg.connect(
            database_url,
            connect_timeout=15,
            application_name="careersignals-production-schema-smoke",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    select c.relname, c.relrowsecurity, c.relforcerowsecurity
                    from pg_catalog.pg_class as c
                    join pg_catalog.pg_namespace as n on n.oid = c.relnamespace
                    where n.nspname = 'public'
                      and c.relkind in ('r', 'p')
                      and c.relname = any(%s)
                    order by c.relname
                    """,
                    (sorted(EXPECTED_RLS_TABLES),),
                )
                validate_rls_rows(cursor.fetchall())
                cursor.execute(
                    """
                    select tablename, policyname, permissive, roles, cmd, qual, with_check
                    from pg_catalog.pg_policies
                    where schemaname = 'public'
                    order by policyname
                    """
                )
                validate_policy_rows(cursor.fetchall())
    except Exception as exc:  # keep credentials and driver messages out of workflow logs
        print(f"Production schema smoke failed ({type(exc).__name__}).")
        return 1

    print(
        "Production schema/RLS metadata smoke passed: "
        f"{len(EXPECTED_RLS_TABLES)} tables are protected and "
        f"the reviewed {len(EXPECTED_RLS_POLICIES)}-policy inventory and minimum invariants are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
