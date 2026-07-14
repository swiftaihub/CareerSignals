from __future__ import annotations

from pathlib import Path
import re

import pytest

from scripts import production_schema_smoke
from scripts.production_schema_smoke import (
    EXPECTED_RLS_POLICIES,
    EXPECTED_RLS_POLICY_TARGETS,
    EXPECTED_RLS_TABLES,
    validate_policy_names,
    validate_policy_rows,
    validate_rls_rows,
)
from tests.rls.test_migration_structure import RLS_TABLES


def _valid_rows() -> list[tuple[str, bool, bool]]:
    return [(name, True, True) for name in sorted(EXPECTED_RLS_TABLES)]


def test_schema_smoke_accepts_all_required_forced_rls_tables() -> None:
    validate_rls_rows(_valid_rows())


def test_schema_smoke_table_contract_matches_migration_contract() -> None:
    assert EXPECTED_RLS_TABLES == RLS_TABLES


def test_schema_smoke_rejects_a_missing_table() -> None:
    with pytest.raises(RuntimeError, match="Missing required public tables"):
        validate_rls_rows(_valid_rows()[1:])


@pytest.mark.parametrize("flags", [(False, True), (True, False), (False, False)])
def test_schema_smoke_rejects_unprotected_tables(flags: tuple[bool, bool]) -> None:
    rows = _valid_rows()
    name = rows[0][0]
    rows[0] = (name, *flags)

    with pytest.raises(RuntimeError, match="RLS is not enabled and forced"):
        validate_rls_rows(rows)


def test_schema_smoke_requires_reviewed_policy_names() -> None:
    active_policies: set[str] = set()
    pattern = re.compile(r"(create policy|drop policy if exists)\s+([a-z0-9_]+)")
    for path in sorted((Path(__file__).parents[1] / "supabase/migrations").glob("*.sql")):
        migration_sql = path.read_text(encoding="utf-8").casefold()
        for operation, name in pattern.findall(migration_sql):
            if operation == "create policy":
                active_policies.add(name)
            else:
                active_policies.discard(name)
    assert EXPECTED_RLS_POLICIES == active_policies
    validate_policy_names(EXPECTED_RLS_POLICIES)
    with pytest.raises(RuntimeError, match="Missing required RLS policies"):
        validate_policy_names(sorted(EXPECTED_RLS_POLICIES)[1:])
    with pytest.raises(RuntimeError, match="Unexpected public RLS policies"):
        validate_policy_names([*EXPECTED_RLS_POLICIES, "unsafe_allow_all"])


def _valid_policy_rows() -> list[tuple[str, str, str, list[str], str, str | None, str | None]]:
    rows = []
    for name, (table, command) in EXPECTED_RLS_POLICY_TARGETS.items():
        markers = ["public.is_current_user_admin()"]
        if "self_or_admin" in name or "current_match_or_admin" in name:
            markers.append("public.current_app_user_uuid()")
        if "active_or_admin" in name or "current_match_or_admin" in name:
            markers.append("public.is_current_user_active()")
        if command in {"INSERT", "UPDATE"} and name != "user_profiles_admin_update":
            markers.extend(["public.current_app_role()", "'demo'"])
        expression = " and ".join(markers)
        using = expression if command in {"SELECT", "UPDATE"} else None
        with_check = expression if command in {"INSERT", "UPDATE"} else None
        rows.append((table, name, "PERMISSIVE", ["authenticated"], command, using, with_check))
    return rows


def test_schema_smoke_validates_policy_targets_roles_commands_and_expressions() -> None:
    rows = _valid_policy_rows()
    validate_policy_rows(rows)

    unsafe = rows.copy()
    table, name, permissive, _roles, command, using, with_check = unsafe[0]
    unsafe[0] = (table, name, permissive, ["public"], command, using, with_check)
    with pytest.raises(RuntimeError, match="metadata differs"):
        validate_policy_rows(unsafe)

    allow_all = rows.copy()
    table, name, permissive, roles, command, using, with_check = allow_all[0]
    allow_all[0] = (table, name, permissive, roles, command, f"({using}) or (true)", with_check)
    with pytest.raises(RuntimeError, match="metadata differs"):
        validate_policy_rows(allow_all)


def test_schema_smoke_connection_errors_do_not_disclose_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_url = "postgresql://user:do-not-print@db.example.invalid/database"
    monkeypatch.setenv("SUPABASE_DB_DIRECT_URL", secret_url)

    def fail_connect(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(f"connection failed for {secret_url}")

    monkeypatch.setattr(production_schema_smoke.psycopg, "connect", fail_connect)
    assert production_schema_smoke.main() == 1
    output = capsys.readouterr().out
    assert "RuntimeError" in output
    assert secret_url not in output


def test_migration_and_release_script_order_is_locked() -> None:
    project_root = Path(__file__).parents[1]
    scripts_dir = project_root / "deployment/backend/scripts"
    if not scripts_dir.exists():
        scripts_dir = project_root / "scripts"
    apply_script = (scripts_dir / "apply-migrations.sh").read_text(encoding="utf-8")
    install_script = (scripts_dir / "install-release.sh").read_text(encoding="utf-8")

    assert apply_script.index("supabase db push --db-url") < apply_script.index(
        "python scripts/production_schema_smoke.py"
    )
    migration_call = install_script.index('bash "$staging_dir/scripts/apply-migrations.sh"')
    assert install_script.index('"${staging_compose[@]}" pull') < migration_call
    assert migration_call < install_script.index(
        'mv -- "$staging_dir" "$release_dir"'
    )
