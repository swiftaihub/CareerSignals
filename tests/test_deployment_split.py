from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts.deployment_split import (
    MANIFEST_NAME,
    SplitValidationError,
    build_repository,
    compare_trees,
    ensure_case_unique,
    safe_symlink_destination,
    validate_manual_only_workflow,
    validate_tree,
)


MANUAL_WORKFLOW = """\
name: Deploy production
on:
  workflow_dispatch:
    inputs:
      revision:
        required: true
        type: string
permissions:
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: echo validated
"""
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_files(root: Path, files: dict[str, str | bytes]) -> None:
    for relative, content in files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            destination.write_bytes(content)
        else:
            destination.write_text(content, encoding="utf-8", newline="\n")


def _commit_repo(tmp_path: Path, files: dict[str, str | bytes]) -> tuple[Path, str]:
    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main", str(repo)],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "split-tests@example.invalid"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Split Tests"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    _write_files(repo, files)
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    ).stdout.strip()
    return repo, sha


def _web_files() -> dict[str, str]:
    return {
        ".gitattributes": "* text=auto eol=lf\n",
        "apps/web/.env.example": "PASSWORD_RECOVERY_COOKIE_SECRET=\n",
        "apps/web/.gitignore": ".env\n.env.*\n!.env.example\n",
        "apps/web/app/page.tsx": "export default function Page() { return null; }\n",
        "apps/web/next.config.mjs": "export default {};\n",
        "apps/web/package-lock.json": '{"lockfileVersion": 3}\n',
        "apps/web/package.json": '{"name": "fixture", "private": true}\n',
        "apps/web/tsconfig.json": "{}\n",
        "deployment/web/.github/workflows/deploy-production.yml": MANUAL_WORKFLOW,
        "deployment/web/README.md": "# Generated Web deployment\n",
        "deployment/web/open-next.config.ts": "export default {};\n",
        "deployment/web/wrangler.jsonc": "{}\n",
    }


def _backend_files() -> dict[str, str]:
    return {
        ".gitattributes": "* text=auto eol=lf\n",
        ".dockerignore": ".env\n",
        ".env.example": "DATABASE_URL=\n",
        ".gitignore": ".env\n.env.*\n!.env.example\n",
        "requirements.txt": "fastapi==1.0\n",
        "requirements.lock": "fastapi==1.0\n",
        "apps/api/main.py": "app = object()\n",
        "apps/scheduler/main.py": "def main(): pass\n",
        "apps/worker/main.py": "def main(): pass\n",
        "apps/web/page.tsx": "must not be copied\n",
        "dbt/dbt_project.yml": "name: fixture\n",
        "dbt/profiles.yml": "fixture: {}\n",
        "data/demo/demo_jobs.json": "[]\n",
        "data/sample/sample_jobs.json": "[]\n",
        "data/raw/private-export.json": "[]\n",
        "deployment/backend/.github/workflows/deploy-production.yml": MANUAL_WORKFLOW,
        "deployment/backend/Dockerfile": "FROM scratch\n",
        "deployment/backend/README.md": "# Generated backend deployment\n",
        "deployment/backend/docker-compose.production.yml": "services: {}\n",
        "deployment/backend/supabase-cli.version": "2.109.1\n",
        "packages/example.py": "VALUE = 1\n",
        "src/example.py": "VALUE = 1\n",
        "supabase/config.toml": "project_id = \"fixture\"\n",
        "supabase/migrations/0001.sql": "select 1;\n",
        "supabase/seed/0001.sql": "select 1;\n",
        "tests/test_fixture.py": "def test_fixture(): assert True\n",
    }


def test_web_split_uses_commit_flattens_source_and_writes_manifest(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _web_files())
    (repo / "apps/web/.env").write_text("PASSWORD_RECOVERY_COOKIE_SECRET=local-only\n")
    (repo / "apps/web/.next").mkdir()
    (repo / "apps/web/.next/local.js").write_text("local build output\n")

    output = tmp_path / "web-output"
    manifest = build_repository(
        repo,
        sha,
        "web",
        output,
        generated_at_utc="2026-07-13T12:00:00Z",
    )

    assert (output / "app/page.tsx").is_file()
    assert not (output / "apps/web").exists()
    assert not (output / ".env").exists()
    assert not (output / ".next").exists()
    assert manifest["source_commit_sha"] == sha
    assert manifest["deployment_target"] == "web"
    assert validate_tree(output, "web", expected_source_sha=sha) == manifest


def test_backend_split_preserves_layout_and_only_allows_fixture_data(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _backend_files())
    output = tmp_path / "backend-output"

    build_repository(repo, sha, "backend", output)

    assert (output / "apps/api/main.py").is_file()
    assert (output / "data/demo/demo_jobs.json").is_file()
    assert (output / "data/sample/sample_jobs.json").is_file()
    assert (output / "supabase/config.toml").is_file()
    assert not (output / "data/raw").exists()
    assert not (output / "apps/web").exists()
    assert not (output / "supabase/.temp").exists()


def test_same_sha_is_deterministic_except_manifest_timestamp(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _web_files())
    first = tmp_path / "first"
    second = tmp_path / "second"

    build_repository(repo, sha, "web", first, generated_at_utc="2026-07-13T12:00:00Z")
    build_repository(repo, sha, "web", second, generated_at_utc="2026-07-13T12:01:00Z")

    assert json.loads((first / MANIFEST_NAME).read_text())["generated_at_utc"] != json.loads(
        (second / MANIFEST_NAME).read_text()
    )["generated_at_utc"]
    compare_trees(first, second)


def test_overlay_collision_requires_explicit_override(tmp_path: Path) -> None:
    files = _web_files()
    files["deployment/web/package.json"] = '{"name": "overlaid"}\n'
    repo, sha = _commit_repo(tmp_path, files)

    with pytest.raises(SplitValidationError, match="Overlay collision"):
        build_repository(repo, sha, "web", tmp_path / "rejected")

    (repo / "deployment/web/.split-overrides").write_text("package.json\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", "deployment/web/.split-overrides"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "allow intentional overlay"],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    allowed_sha = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
    ).stdout.strip()
    output = tmp_path / "allowed"
    build_repository(repo, allowed_sha, "web", output)
    assert json.loads((output / "package.json").read_text())["name"] == "overlaid"


def test_secret_failure_never_prints_matched_value(tmp_path: Path) -> None:
    secret = "ghp_" + ("A" * 30)
    files = _web_files()
    files["deployment/web/unsafe.txt"] = secret + "\n"
    repo, sha = _commit_repo(tmp_path, files)

    with pytest.raises(SplitValidationError) as raised:
        build_repository(repo, sha, "web", tmp_path / "unsafe")

    assert "github-token" in str(raised.value)
    assert secret not in str(raised.value)


def test_manifest_detects_post_build_tampering(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _web_files())
    output = tmp_path / "web-output"
    build_repository(repo, sha, "web", output)
    (output / "app/page.tsx").write_text("tampered\n", encoding="utf-8", newline="\n")

    with pytest.raises(SplitValidationError, match="inventory"):
        validate_tree(output, "web", expected_source_sha=sha)


def test_validation_ignores_checkout_git_metadata(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _backend_files())
    output = tmp_path / "backend-output"
    build_repository(repo, sha, "backend", output)
    subprocess.run(
        ["git", "init", "-b", "main", str(output)],
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )

    validate_tree(output, "backend", expected_source_sha=sha)


def test_case_collisions_and_symlink_escapes_are_rejected() -> None:
    with pytest.raises(SplitValidationError, match="Case-insensitive"):
        ensure_case_unique(["components/Card.tsx", "components/card.tsx"])
    with pytest.raises(SplitValidationError, match="Case-insensitive"):
        ensure_case_unique(["Components/card.tsx", "components/table.tsx"])
    with pytest.raises(SplitValidationError, match="escapes"):
        safe_symlink_destination("nested/link", "../../outside")
    assert safe_symlink_destination("nested/link", "../target") == "target"


def test_workflow_trigger_validation_is_manual_only(tmp_path: Path) -> None:
    manual = tmp_path / "manual.yml"
    manual.write_text(MANUAL_WORKFLOW, encoding="utf-8")
    validate_manual_only_workflow(manual)

    for event in ("push", "schedule", "pull_request"):
        unsafe = tmp_path / f"{event}.yml"
        unsafe.write_text(
            f"name: unsafe\non:\n  workflow_dispatch:\n  {event}:\njobs: {{}}\n",
            encoding="utf-8",
        )
        with pytest.raises(SplitValidationError, match="manual-only"):
            validate_manual_only_workflow(unsafe)


def test_missing_deployment_files_are_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SplitValidationError, match="Missing required files"):
        validate_tree(empty, "web", require_manifest=False)


def test_generated_deployment_text_rejects_crlf(tmp_path: Path) -> None:
    repo, sha = _commit_repo(tmp_path, _web_files())
    output = tmp_path / "web-output"
    build_repository(repo, sha, "web", output)
    workflow = output / ".github/workflows/deploy-production.yml"
    workflow.write_bytes(workflow.read_bytes().replace(b"\n", b"\r\n"))

    with pytest.raises(SplitValidationError, match="LF line endings"):
        validate_tree(output, "web", expected_source_sha=sha)


def test_additional_automatic_workflow_in_split_is_rejected(tmp_path: Path) -> None:
    files = _web_files()
    files["deployment/web/.github/workflows/unsafe.yml"] = (
        "name: unsafe\non:\n  push:\njobs: {}\n"
    )
    repo, sha = _commit_repo(tmp_path, files)
    with pytest.raises(SplitValidationError, match="manual-only"):
        build_repository(repo, sha, "web", tmp_path / "unsafe-workflow")


def test_canonical_sync_workflow_is_manual_only_with_safe_defaults() -> None:
    workflow = PROJECT_ROOT / ".github/workflows/sync-deployment-repositories.yml"
    if not workflow.exists():
        pytest.skip("canonical sync workflow is intentionally absent from generated deployment repositories")
    validate_manual_only_workflow(workflow)
    text = workflow.read_text(encoding="utf-8")
    for input_name in ("source_ref", "target_branch", "sync_web", "sync_backend", "dry_run"):
        assert f"      {input_name}:" in text
    source_ref_block = text.split("      source_ref:", 1)[1].split("      target_branch:", 1)[0]
    assert "default:" not in source_ref_block
    assert "full 40-character SHA" in source_ref_block
    dry_run_block = text.split("      dry_run:", 1)[1].split("\n\n", 1)[0]
    assert "default: true" in dry_run_block
    assert "ref: ${{ github.sha }}" in text
    assert "ref: ${{ inputs.source_ref }}" not in text
    assert '"${TARGET_BRANCH}" == "main" && ! "${SOURCE_REF}" =~ ^[0-9a-f]{40}$' in text
    assert '"$GITHUB_REF" != "refs/heads/main"' in text
    assert 'git merge-base --is-ancestor "$workflow_sha" origin/main' in text
    assert 'git merge-base --is-ancestor "${source_sha}" origin/main' in text
    assert "--force" not in text
