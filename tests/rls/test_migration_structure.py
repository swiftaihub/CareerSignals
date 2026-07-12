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
    "0015_config_bundle_revisions.sql",
    "0016_pipeline_quota_resets.sql",
]

RLS_TABLES = {
    "user_profiles",
    "user_config_documents",
    "user_config_versions",
    "config_bundle_revisions",
    "skill_alias_catalog",
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
        _sql(name)
        for name in (
            "0010_rls_policies.sql",
            "0013_global_bootstrap_pipeline.sql",
            "0015_config_bundle_revisions.sql",
        )
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


def test_config_bundles_are_atomic_tenant_scoped_and_pipeline_bound() -> None:
    migration = _sql("0015_config_bundle_revisions.sql")

    assert "create table public.config_bundle_revisions" in migration
    assert "compiled_overrides jsonb not null" in migration
    assert "compiled_configs jsonb" in migration
    assert "config_revision_map jsonb not null" in migration
    assert "user_config_versions_one_type_per_bundle" in migration
    assert "foreign key (user_uuid, bundle_revision_uuid)" in migration
    assert "add column config_bundle_revision_uuid uuid" in migration
    assert "user_pipeline_runs_bundle_user_fk" in migration
    assert "config_bundle_revisions_append_only" in migration
    assert "config_bundle_revisions_reject_demo_mutation" in migration
    assert "config_bundle_revisions_self_or_admin_select" in migration


def test_shared_skill_alias_catalog_has_normalized_dedup_and_admin_only_rls() -> None:
    migration = _sql("0015_config_bundle_revisions.sql")

    assert "create table public.skill_alias_catalog" in migration
    assert "unique (normalized_canonical_skill, normalized_alias)" in migration
    assert "confidence between 0 and 1" in migration
    assert "skill_alias_catalog_admin_select" in migration
    assert "using (public.is_current_user_admin())" in migration


def test_pipeline_quota_reset_marker_preserves_run_history() -> None:
    migration = _sql("0016_pipeline_quota_resets.sql")

    assert "add column pipeline_quota_reset_at timestamptz" in migration
    assert "user_profiles_pipeline_quota_reset_idx" in migration
    assert "delete from public.user_pipeline_runs" not in migration


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
