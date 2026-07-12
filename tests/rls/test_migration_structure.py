from pathlib import Path
import re


MIGRATIONS = Path("supabase/migrations")
EXPECTED_MIGRATIONS = [
    "0001_extensions_and_enums.sql",
    "0002_user_profiles.sql",
    "0003_user_configs.sql",
    "0004_entitlements_and_billing.sql",
    "0005_connector_refresh_runs.sql",
    "0006_user_pipeline_runs.sql",
    "0007_job_serving_tables.sql",
    "0008_activity_and_audit.sql",
    "0009_functions_and_triggers.sql",
    "0010_rls_policies.sql",
    "0011_indexes_and_constraints.sql",
    "0012_pipeline_waiting_status.sql",
    "0013_global_bootstrap_pipeline.sql",
    "0014_cumulative_personal_results.sql",
]

RLS_TABLES = {
    "user_profiles",
    "user_config_documents",
    "user_config_versions",
    "entitlement_events",
    "billing_events",
    "connector_refresh_runs",
    "connector_source_runs",
    "connector_run_user_config_snapshots",
    "connector_acquisition_queries",
    "user_pipeline_runs",
    "user_pipeline_run_events",
    "user_bootstrap_workflows",
    "job_postings",
    "user_job_matches",
    "user_job_statuses",
    "user_category_summary",
    "user_skill_gap",
    "user_company_priority",
    "user_activity_events",
    "admin_audit_logs",
}


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8").casefold()


def test_migration_names_are_complete_and_deterministic() -> None:
    assert sorted(path.name for path in MIGRATIONS.glob("*.sql")) == EXPECTED_MIGRATIONS


def test_every_control_plane_table_is_created() -> None:
    combined = "\n".join(_sql(name) for name in EXPECTED_MIGRATIONS)
    for table in RLS_TABLES:
        assert f"create table public.{table}" in combined


def test_rls_is_enabled_and_forced_for_every_table() -> None:
    rls_sql = "\n".join(
        _sql(name) for name in ("0010_rls_policies.sql", "0013_global_bootstrap_pipeline.sql")
    )
    for table in RLS_TABLES:
        assert f"alter table public.{table} enable row level security" in rls_sql
        assert f"alter table public.{table} force row level security" in rls_sql


def test_security_and_trigger_functions_fix_search_path() -> None:
    functions_sql = "\n".join(_sql(name) for name in EXPECTED_MIGRATIONS)
    function_blocks = re.findall(
        r"create or replace function\s+public\.[\s\S]+?\$function\$;",
        functions_sql,
    )
    assert function_blocks
    assert all("set search_path = pg_catalog, public" in block for block in function_blocks)


def test_tenant_and_publication_uniqueness_guards_exist() -> None:
    constraint_sql = _sql("0011_indexes_and_constraints.sql")
    assert "create unique index one_active_pipeline_per_user" in constraint_sql
    assert "create unique index one_active_bootstrap_workflow_per_user" in _sql("0013_global_bootstrap_pipeline.sql")
    assert "create unique index one_current_pipeline_result_per_user" in constraint_sql
    assert "create unique index user_job_matches_one_current_job" in constraint_sql
    assert "where status in ('queued', 'running')" in constraint_sql
    assert "where status in ('queued', 'waiting_for_global', 'running')" in _sql("0013_global_bootstrap_pipeline.sql")


def test_cumulative_personal_result_lineage_is_migrated() -> None:
    migration = _sql("0014_cumulative_personal_results.sql")
    for table in (
        "user_job_matches",
        "user_category_summary",
        "user_skill_gap",
        "user_company_priority",
    ):
        assert f"alter table public.{table}" in migration
        assert "first_created_run_uuid" in migration
        assert "last_updated_run_uuid" in migration
        assert "last_evaluated_run_uuid" in migration
        assert "deactivation_reason" in migration
        assert "deactivated_run_uuid" in migration

    assert "upr.status in ('running', 'completed')" in migration
    assert "does not require the latest-result run" in migration


def test_demo_seed_is_fixed_read_only_and_has_exactly_twenty_jobs() -> None:
    seed = Path("supabase/seed/0001_demo.sql").read_text(encoding="utf-8").casefold()
    assert "insert into auth.users" not in seed
    assert seed.count("('demo-job-") == 20
    assert "current_demo_jobs <> 20" in seed
    assert "careersignals.allow_demo_seed" in seed


def test_migrations_do_not_embed_credentials_or_touch_cli_state() -> None:
    combined = "\n".join(_sql(name) for name in EXPECTED_MIGRATIONS)
    assert "supabase/.temp" not in combined
    assert "supabase_service_role_key=" not in combined
    assert "motherduck_token=" not in combined
    assert "eyjhb" not in combined
