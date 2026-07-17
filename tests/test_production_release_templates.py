from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    canonical = ROOT / relative
    if canonical.is_file():
        return canonical.read_text(encoding="utf-8")

    backend_prefix = "deployment/backend/"
    if relative.startswith(backend_prefix):
        flattened = ROOT / relative.removeprefix(backend_prefix)
        if flattened.is_file():
            return flattened.read_text(encoding="utf-8")

    if relative.startswith("deployment/web/"):
        pytest.skip("web deployment templates are intentionally absent from the backend split")
    raise FileNotFoundError(relative)


def test_installer_uses_one_root_owned_archive_for_validation_and_extraction() -> None:
    script = _read("deployment/backend/scripts/install-release.sh")

    assert 'install -m 600 -o root -g root -- "$archive" "$trusted_archive"' in script
    assert "256 * 1024 * 1024" in script
    assert 'python3 - "$trusted_archive"' in script
    assert '--file "$trusted_archive"' in script
    assert "duplicate member path" in script
    assert "required path with the wrong type" in script


def test_installer_binds_manifest_validation_to_the_staging_directory() -> None:
    script = _read("deployment/backend/scripts/install-release.sh")

    assert '--manifest "$staging_dir/SOURCE_MANIFEST.json"' in script


def test_migration_dry_run_and_apply_are_bound_to_the_release_directory() -> None:
    script = _read("deployment/backend/scripts/apply-migrations.sh")

    assert script.count('cd "$release_dir"') == 2
    assert "supabase db push --dry-run" in script
    assert "supabase db push --db-url" in script


def test_backend_workflow_prepares_local_dbt_storage_inside_checkout() -> None:
    workflow = _read("deployment/backend/.github/workflows/deploy-production.yml")

    assert "mkdir -p data/local" in workflow
    assert workflow.count("cd dbt") == 2
    assert 'test -z "$BACKUP_REFERENCE"' in workflow
    assert '[[ "$IMAGE_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]]' in workflow


def test_web_production_smoke_requires_the_backend_source_sha() -> None:
    workflow = _read("deployment/web/.github/workflows/deploy-production.yml")
    smoke = _read("deployment/web/scripts/smoke-test.mjs")

    assert "EXPECTED_SOURCE_SHA: ${{ inputs.expected_source_sha }}" in workflow
    assert '== sb_publishable_*' in workflow
    assert 'payload?.source_commit_sha !== expectedSourceSha' in smoke


def test_rollback_revalidates_the_selected_release_manifest() -> None:
    script = _read("deployment/backend/scripts/rollback.sh")

    assert '--expected-sha "$(basename "$release")"' in script
    assert '--manifest "$release/SOURCE_MANIFEST.json"' in script


def test_backend_health_check_is_bound_to_the_release_source_sha() -> None:
    script = _read("deployment/backend/scripts/health-check.sh")

    assert 'expected_source_sha="$(basename "$release_dir")"' in script
    assert 'payload.get("source_commit_sha") != os.environ["EXPECTED_SOURCE_SHA"]' in script


def test_backend_health_check_reports_bounded_redacted_service_logs_once() -> None:
    script = _read("deployment/backend/scripts/health-check.sh")

    assert '--tail 80 "$service"' in script
    assert "credentials redacted" in script
    assert "[REDACTED]" in script
    assert 'careersignals-health-${expected_source_sha}-${service}.logged' in script
    assert '"$reason" != "health is starting"' in script


def test_duckdb_extension_tmpfs_allows_native_motherduck_loading() -> None:
    compose = _read("deployment/backend/docker-compose.production.yml")
    mount = next(
        line.strip()
        for line in compose.splitlines()
        if "/home/careersignals/.duckdb:" in line
    )

    assert ":rw,exec,nosuid,nodev," in mount
    assert "noexec" not in mount
    assert "/tmp:rw,noexec,nosuid" in compose
    assert "/app/dbt/target:rw,noexec,nosuid" in compose
