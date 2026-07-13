"""Deterministically build and validate generated deployment repositories.

The splitter reads a Git archive for a resolved commit. It never copies the
caller's working tree, so ignored credentials and local build output cannot be
included accidentally.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from typing import Iterable, Sequence


SOURCE_REPOSITORY = "swiftaihub/CareerSignals"
MANIFEST_NAME = "SOURCE_MANIFEST.json"
OVERRIDE_FILE = ".split-overrides"
TARGETS = ("web", "backend")


class SplitValidationError(RuntimeError):
    """Raised when source or generated deployment content is unsafe."""


@dataclass(frozen=True)
class ArchiveRecord:
    path: str
    kind: str
    data: bytes
    mode: int


@dataclass(frozen=True)
class OutputRecord:
    source_path: str
    output_path: str
    kind: str
    data: bytes
    mode: int
    overlay: bool


BACKEND_ROOT_FILES = frozenset(
    {
        ".gitattributes",
        ".dockerignore",
        ".env.example",
        ".gitignore",
        "pyproject.toml",
        "pytest.ini",
        "requirements.txt",
        "requirements.lock",
        "setup.cfg",
        "tox.ini",
        "uv.lock",
    }
)
BACKEND_EXACT_FILES = frozenset({"apps/__init__.py", "supabase/config.toml"})
BACKEND_PREFIXES = (
    "apps/api/",
    "apps/worker/",
    "apps/scheduler/",
    "packages/",
    "src/",
    "config/",
    "dbt/",
    "scripts/",
    "supabase/migrations/",
    "supabase/seed/",
    "tests/",
    "data/demo/",
    "data/sample/",
)

REQUIRED_FILES = {
    "web": frozenset(
        {
            ".gitattributes",
            ".env.example",
            ".gitignore",
            ".github/workflows/deploy-production.yml",
            "README.md",
            "next.config.mjs",
            "open-next.config.ts",
            "package-lock.json",
            "package.json",
            "tsconfig.json",
            "wrangler.jsonc",
        }
    ),
    "backend": frozenset(
        {
            ".gitattributes",
            ".dockerignore",
            ".env.example",
            ".gitignore",
            ".github/workflows/deploy-production.yml",
            "Dockerfile",
            "README.md",
            "apps/api/main.py",
            "apps/scheduler/main.py",
            "apps/worker/main.py",
            "dbt/dbt_project.yml",
            "dbt/profiles.yml",
            "docker-compose.production.yml",
            "requirements.txt",
            "requirements.lock",
            "supabase-cli.version",
        }
    ),
}

FORBIDDEN_COMPONENTS = frozenset(
    {
        ".git",
        ".next",
        ".open-next",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".supabase",
        ".temp",
        ".venv",
        ".worker-next",
        "__pycache__",
        "coverage",
        "htmlcov",
        "node_modules",
        "outputs",
    }
)
FORBIDDEN_FILENAMES = frozenset(
    {
        "credentials.json",
        "service-account.json",
    }
)
FORBIDDEN_SUFFIXES = (
    ".db",
    ".duckdb",
    ".duckdb.wal",
    ".jks",
    ".key",
    ".keystore",
    ".p12",
    ".pem",
    ".pfx",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".tsbuildinfo",
    ".xlsx",
)

LF_REQUIRED_FILENAMES = frozenset(
    {
        ".dockerignore",
        ".env.example",
        ".gitattributes",
        ".gitignore",
        ".split-overrides",
        "Caddyfile",
        "Dockerfile",
        "requirements.lock",
        "_headers",
    }
)
LF_REQUIRED_SUFFIXES = frozenset(
    {
        ".cfg",
        ".css",
        ".html",
        ".js",
        ".json",
        ".jsonc",
        ".lock",
        ".md",
        ".mjs",
        ".py",
        ".service",
        ".sh",
        ".sql",
        ".toml",
        ".ts",
        ".tsx",
        ".txt",
        ".version",
        ".yaml",
        ".yml",
    }
)

_SECRET_RULES: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private-key-material",
        re.compile(br"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ),
    ("github-token", re.compile(br"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github-fine-grained-token", re.compile(br"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("aws-access-key", re.compile(br"\bAKIA[0-9A-Z]{16}\b")),
    ("google-api-key", re.compile(br"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "jwt-token",
        re.compile(br"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    ("supabase-secret-key", re.compile(br"\bsb_secret_[A-Za-z0-9_-]{15,}\b")),
    ("openai-style-key", re.compile(br"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("stripe-live-key", re.compile(br"\bsk_live_[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(br"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    (
        "credential-bearing-url",
        re.compile(
            br"(?:https?|postgres(?:ql)?|mysql|mongodb(?:\+srv)?)://"
            br"[^\s/:@]+:[^\s/@]+@[^\s]+",
            re.IGNORECASE,
        ),
    ),
    ("literal-bearer-token", re.compile(br"\bBearer\s+[A-Za-z0-9._~+/-]{24,}\b")),
)
_PLACEHOLDER_MARKERS = (
    b"${{",
    b"{{",
    b"changeme",
    b"dummy",
    b"example",
    b"fake",
    b"invalid",
    b"localhost",
    b"placeholder",
    b"postgres:postgres",
    b"replace",
    b"test",
    b"user:pass",
    b"username:password",
)


def _run_git(repo_root: Path, args: Sequence[str], *, binary: bool = False) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise SplitValidationError(f"Git command failed: {message or 'unknown Git error'}")
    if binary:
        return result.stdout
    return result.stdout.decode("utf-8", errors="strict").strip()


def resolve_commit(repo_root: Path, source_ref: str) -> str:
    """Resolve a user-provided ref to one full commit SHA."""

    if not source_ref or source_ref.startswith("-") or any(ch.isspace() for ch in source_ref):
        raise SplitValidationError("source_ref is not a safe Git revision")
    resolved = str(
        _run_git(repo_root, ["rev-parse", "--verify", "--end-of-options", f"{source_ref}^{{commit}}"])
    )
    if not re.fullmatch(r"[0-9a-f]{40}", resolved):
        raise SplitValidationError("source_ref did not resolve to a full commit SHA")
    return resolved


def _commit_timestamp(repo_root: Path, source_sha: str) -> str:
    value = str(_run_git(repo_root, ["show", "-s", "--format=%cI", source_sha]))
    return _normalize_timestamp(value)


def _source_branch(repo_root: Path, source_sha: str) -> str:
    for ref, label in (("origin/main", "main"), ("main", "main"), ("origin/dev", "dev"), ("dev", "dev")):
        exists = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", ref],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if exists.returncode:
            continue
        ancestor = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", source_sha, ref],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if not ancestor.returncode:
            return label
    return "detached"


def _normalize_timestamp(value: str | None) -> str:
    if value is None:
        parsed = datetime.now(timezone.utc)
    else:
        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise SplitValidationError("generated timestamp must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise SplitValidationError("generated timestamp must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_relative_path(value: str, *, description: str) -> str:
    if not value or "\\" in value or value.startswith("/"):
        raise SplitValidationError(f"Unsafe {description} path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise SplitValidationError(f"Unsafe {description} path")
    return path.as_posix()


def ensure_case_unique(paths: Iterable[str]) -> None:
    """Reject output paths that collide on case-insensitive filesystems."""

    seen: dict[str, str] = {}
    for raw_path in paths:
        path = _safe_relative_path(raw_path, description="output")
        parts = PurePosixPath(path).parts
        for depth in range(1, len(parts) + 1):
            prefix = PurePosixPath(*parts[:depth]).as_posix()
            folded = prefix.casefold()
            previous = seen.get(folded)
            if previous is not None and previous != prefix:
                raise SplitValidationError(
                    f"Case-insensitive path collision: {previous} and {prefix}"
                )
            seen[folded] = prefix


def safe_symlink_destination(link_path: str, link_target: str) -> str:
    """Return an in-tree normalized symlink destination or reject an escape."""

    link = PurePosixPath(_safe_relative_path(link_path, description="symlink"))
    if not link_target or "\\" in link_target or link_target.startswith("/"):
        raise SplitValidationError(f"Symlink escapes deployment tree: {link_path}")
    parts = list(link.parent.parts)
    for part in PurePosixPath(link_target).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise SplitValidationError(f"Symlink escapes deployment tree: {link_path}")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise SplitValidationError(f"Symlink has no in-tree destination: {link_path}")
    return PurePosixPath(*parts).as_posix()


def _read_archive(repo_root: Path, source_sha: str) -> list[ArchiveRecord]:
    archive = bytes(
        _run_git(
            repo_root,
            ["-c", "core.autocrlf=false", "archive", "--format=tar", source_sha],
            binary=True,
        )
    )
    records: list[ArchiveRecord] = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle:
            if member.isdir():
                continue
            path = _safe_relative_path(member.name.rstrip("/"), description="archive")
            if member.isfile():
                extracted = bundle.extractfile(member)
                if extracted is None:
                    raise SplitValidationError(f"Unable to read tracked file: {path}")
                records.append(ArchiveRecord(path, "file", extracted.read(), member.mode))
            elif member.issym():
                target = member.linkname.encode("utf-8")
                records.append(ArchiveRecord(path, "symlink", target, member.mode))
            else:
                raise SplitValidationError(f"Unsupported tracked archive entry: {path}")
    return records


def _base_output_path(path: str, target: str) -> str | None:
    if path == ".gitattributes":
        return path
    if target == "web":
        prefix = "apps/web/"
        return path[len(prefix) :] if path.startswith(prefix) else None

    if path in BACKEND_ROOT_FILES or path in BACKEND_EXACT_FILES:
        return path
    if any(path.startswith(prefix) for prefix in BACKEND_PREFIXES):
        return path
    return None


def _overlay_output_path(path: str, target: str) -> str | None:
    prefix = f"deployment/{target}/"
    if not path.startswith(prefix):
        return None
    relative = path[len(prefix) :]
    return relative or None


def _parse_overrides(records: Sequence[ArchiveRecord], target: str) -> set[str]:
    metadata_path = f"deployment/{target}/{OVERRIDE_FILE}"
    matches = [record for record in records if record.path == metadata_path]
    if not matches:
        return set()
    record = matches[0]
    if record.kind != "file":
        raise SplitValidationError(f"{metadata_path} must be a regular file")
    try:
        text = record.data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SplitValidationError(f"{metadata_path} must be UTF-8") from exc
    overrides: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        overrides.add(_safe_relative_path(line, description="override"))
    ensure_case_unique(overrides)
    return overrides


def _validate_output_path(path: str, target: str) -> None:
    normalized = _safe_relative_path(path, description="deployment")
    pure = PurePosixPath(normalized)
    folded_parts = tuple(part.casefold() for part in pure.parts)
    filename = folded_parts[-1]

    if any(part in FORBIDDEN_COMPONENTS or part.startswith(".venv") for part in folded_parts):
        raise SplitValidationError(f"Forbidden generated/local path: {normalized}")
    if filename.startswith(".env") and filename != ".env.example":
        raise SplitValidationError(f"Forbidden environment file: {normalized}")
    if filename in FORBIDDEN_FILENAMES or filename.endswith(FORBIDDEN_SUFFIXES):
        raise SplitValidationError(f"Forbidden credential/generated file: {normalized}")
    if target == "backend" and folded_parts[0] == "data":
        if len(folded_parts) < 2 or folded_parts[1] not in {"demo", "sample"}:
            raise SplitValidationError(f"Forbidden backend data path: {normalized}")
    if target == "backend" and normalized.startswith("apps/web/"):
        raise SplitValidationError(f"Frontend file present in backend split: {normalized}")


def _plan_output(records: Sequence[ArchiveRecord], target: str) -> dict[str, OutputRecord]:
    overrides = _parse_overrides(records, target)
    planned: dict[str, OutputRecord] = {}
    case_paths: dict[str, str] = {}
    used_overrides: set[str] = set()

    for overlay in (False, True):
        for record in records:
            output_path = (
                _overlay_output_path(record.path, target)
                if overlay
                else _base_output_path(record.path, target)
            )
            if output_path is None or output_path == OVERRIDE_FILE:
                continue
            output_path = _safe_relative_path(output_path, description="output")
            _validate_output_path(output_path, target)
            folded = output_path.casefold()
            previous_case = case_paths.get(folded)
            if previous_case is not None and previous_case != output_path:
                raise SplitValidationError(
                    f"Case-insensitive path collision: {previous_case} and {output_path}"
                )
            previous = planned.get(output_path)
            if previous is not None:
                if not overlay or output_path not in overrides:
                    raise SplitValidationError(
                        f"Overlay collision requires deployment/{target}/{OVERRIDE_FILE}: {output_path}"
                    )
                used_overrides.add(output_path)
            planned[output_path] = OutputRecord(
                source_path=record.path,
                output_path=output_path,
                kind=record.kind,
                data=record.data,
                mode=record.mode,
                overlay=overlay,
            )
            case_paths[folded] = output_path

    stale = overrides - used_overrides
    if stale:
        raise SplitValidationError(
            f"Unused overlay override entries for {target}: {', '.join(sorted(stale))}"
        )
    if not planned:
        raise SplitValidationError(f"No tracked content selected for {target}")
    ensure_case_unique(planned)

    for record in planned.values():
        if record.kind != "symlink":
            continue
        try:
            target_value = record.data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SplitValidationError(f"Symlink target is not UTF-8: {record.output_path}") from exc
        destination = safe_symlink_destination(record.output_path, target_value)
        if destination not in planned and not any(
            candidate.startswith(destination.rstrip("/") + "/") for candidate in planned
        ):
            raise SplitValidationError(f"Symlink destination is not included: {record.output_path}")
    return planned


def _write_plan(root: Path, plan: dict[str, OutputRecord]) -> None:
    for output_path in sorted(plan):
        record = plan[output_path]
        destination = root.joinpath(*PurePosixPath(output_path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if record.kind == "symlink":
            os.symlink(record.data.decode("utf-8"), destination)
            continue
        destination.write_bytes(record.data)
        if record.mode & stat.S_IXUSR:
            destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _walk_paths(root: Path) -> list[tuple[str, Path]]:
    paths: list[tuple[str, Path]] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        paths.append((_safe_relative_path(relative, description="generated"), path))
    return sorted(paths)


def _scan_secret_patterns(path: str, content: bytes) -> None:
    for rule_name, pattern in _SECRET_RULES:
        for match in pattern.finditer(content):
            candidate = match.group(0).lower()
            if any(marker in candidate for marker in _PLACEHOLDER_MARKERS):
                continue
            raise SplitValidationError(f"Possible secret pattern ({rule_name}) in {path}")


def _require_lf_line_endings(path: str, content: bytes) -> None:
    pure = PurePosixPath(path)
    if pure.name in LF_REQUIRED_FILENAMES or pure.suffix.casefold() in LF_REQUIRED_SUFFIXES:
        if b"\r" in content:
            raise SplitValidationError(f"Deployment text must use LF line endings: {path}")


def validate_manual_only_workflow(path: Path) -> None:
    """Strictly accept a workflow whose only top-level event is workflow_dispatch."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise SplitValidationError(f"Unable to read workflow: {path}") from exc
    on_indices: list[int] = []
    for index, raw in enumerate(lines):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw == raw.lstrip() and re.match(r"^(?:on|['\"]on['\"]):", raw):
            on_indices.append(index)
    if len(on_indices) != 1:
        raise SplitValidationError(f"Workflow must contain exactly one top-level on block: {path}")

    index = on_indices[0]
    _, inline = lines[index].split(":", 1)
    inline = inline.split("#", 1)[0].strip()
    if inline:
        normalized = inline.strip("[] ")
        events = {item.strip(" '\"") for item in normalized.split(",") if item.strip()}
    else:
        events: set[str] = set()
        child_indent: int | None = None
        for raw in lines[index + 1 :]:
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            indent = len(raw) - len(raw.lstrip(" "))
            if not indent:
                break
            if child_indent is None:
                child_indent = indent
            if indent != child_indent:
                continue
            match = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_-]*):", raw)
            if not match:
                raise SplitValidationError(f"Workflow on block uses unsupported syntax: {path}")
            events.add(match.group(1))
    if events != {"workflow_dispatch"}:
        safe_events = ", ".join(sorted(events)) if events else "none"
        raise SplitValidationError(
            f"Workflow must be manual-only (found events: {safe_events}): {path}"
        )


def _entry_bytes(path: Path) -> tuple[str, bytes]:
    if path.is_symlink():
        return "symlink", os.readlink(path).encode("utf-8")
    return "file", path.read_bytes()


def _inventory(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for relative, path in _walk_paths(root):
        if relative == MANIFEST_NAME:
            continue
        kind, content = _entry_bytes(path)
        entries.append(
            {
                "path": relative,
                "kind": kind,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return entries


def _content_digest(files: Sequence[dict[str, object]]) -> str:
    encoded = json.dumps(list(files), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_manifest(
    root: Path,
    *,
    repo_root: Path,
    source_sha: str,
    target: str,
    generated_at_utc: str | None,
    source_repository: str,
) -> dict[str, object]:
    files = _inventory(root)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "source_repository": source_repository,
        "source_branch": _source_branch(repo_root, source_sha),
        "source_commit_sha": source_sha,
        "source_commit_timestamp_utc": _commit_timestamp(repo_root, source_sha),
        "generated_at_utc": _normalize_timestamp(generated_at_utc),
        "deployment_target": target,
        "file_count": len(files),
        "content_digest_sha256": _content_digest(files),
        "files": files,
    }
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def _load_manifest(root: Path) -> dict[str, object]:
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise SplitValidationError(f"Missing required file: {MANIFEST_NAME}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SplitValidationError("SOURCE_MANIFEST.json is not valid UTF-8 JSON") from exc
    if not isinstance(manifest, dict):
        raise SplitValidationError("SOURCE_MANIFEST.json must contain an object")
    return manifest


def validate_tree(
    root: Path,
    target: str,
    *,
    require_manifest: bool = True,
    expected_source_sha: str | None = None,
) -> dict[str, object] | None:
    """Validate filenames, links, secrets, required files, workflows, and manifest."""

    if target not in TARGETS:
        raise SplitValidationError(f"Unsupported deployment target: {target}")
    root = root.resolve()
    if not root.is_dir():
        raise SplitValidationError(f"Deployment tree does not exist: {root}")
    walked = _walk_paths(root)
    relative_paths = [relative for relative, _ in walked]
    ensure_case_unique(relative_paths)

    for relative, path in walked:
        _validate_output_path(relative, target)
        if path.is_symlink():
            destination = safe_symlink_destination(relative, os.readlink(path))
            resolved = (root / Path(*PurePosixPath(destination).parts)).resolve(strict=False)
            if root != resolved and root not in resolved.parents:
                raise SplitValidationError(f"Symlink escapes deployment tree: {relative}")
            continue
        content = path.read_bytes()
        _require_lf_line_endings(relative, content)
        _scan_secret_patterns(relative, content)

    missing = sorted(REQUIRED_FILES[target] - set(relative_paths))
    if missing:
        raise SplitValidationError(f"Missing required files for {target}: {', '.join(missing)}")
    workflow_root = root / ".github" / "workflows"
    workflows = sorted(
        path
        for path in workflow_root.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".yml", ".yaml"}
    )
    for workflow in workflows:
        validate_manual_only_workflow(workflow)

    if not require_manifest:
        return None
    manifest = _load_manifest(root)
    if manifest.get("deployment_target") != target:
        raise SplitValidationError("Manifest deployment_target does not match validation target")
    source_sha = manifest.get("source_commit_sha")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise SplitValidationError("Manifest source_commit_sha is not a full SHA")
    if expected_source_sha is not None and source_sha != expected_source_sha:
        raise SplitValidationError("Manifest source SHA does not match the expected source SHA")
    generated_at = manifest.get("generated_at_utc")
    if not isinstance(generated_at, str):
        raise SplitValidationError("Manifest generated_at_utc is missing")
    _normalize_timestamp(generated_at)
    actual_files = _inventory(root)
    if manifest.get("files") != actual_files:
        raise SplitValidationError("Manifest file inventory does not match generated content")
    if manifest.get("file_count") != len(actual_files):
        raise SplitValidationError("Manifest file_count does not match generated content")
    if manifest.get("content_digest_sha256") != _content_digest(actual_files):
        raise SplitValidationError("Manifest content digest does not match generated content")
    return manifest


def build_repository(
    repo_root: Path,
    source_ref: str,
    target: str,
    output: Path,
    *,
    generated_at_utc: str | None = None,
    source_repository: str = SOURCE_REPOSITORY,
) -> dict[str, object]:
    """Build one validated deployment tree from tracked content at source_ref."""

    repo_root = repo_root.resolve()
    output = output.resolve()
    if target not in TARGETS:
        raise SplitValidationError(f"Unsupported deployment target: {target}")
    source_sha = resolve_commit(repo_root, source_ref)
    records = _read_archive(repo_root, source_sha)
    plan = _plan_output(records, target)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and any(output.iterdir()):
        raise SplitValidationError(f"Output directory must be absent or empty: {output}")
    if output.exists():
        output.rmdir()

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-{target}-", dir=output.parent))
    try:
        _write_plan(staging, plan)
        validate_tree(staging, target, require_manifest=False)
        manifest = _write_manifest(
            staging,
            repo_root=repo_root,
            source_sha=source_sha,
            target=target,
            generated_at_utc=generated_at_utc,
            source_repository=source_repository,
        )
        validate_tree(staging, target, expected_source_sha=source_sha)
        os.replace(staging, output)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def compare_trees(left: Path, right: Path) -> None:
    """Require byte equality except for generated_at_utc in the manifest."""

    left_paths = dict(_walk_paths(left.resolve()))
    right_paths = dict(_walk_paths(right.resolve()))
    if set(left_paths) != set(right_paths):
        raise SplitValidationError("Generated trees contain different path sets")
    for relative in sorted(left_paths):
        left_kind, left_content = _entry_bytes(left_paths[relative])
        right_kind, right_content = _entry_bytes(right_paths[relative])
        if left_kind != right_kind:
            raise SplitValidationError(f"Generated entry kind differs: {relative}")
        if relative == MANIFEST_NAME:
            left_manifest = json.loads(left_content)
            right_manifest = json.loads(right_content)
            left_manifest.pop("generated_at_utc", None)
            right_manifest.pop("generated_at_utc", None)
            if left_manifest != right_manifest:
                raise SplitValidationError("Generated manifests differ beyond generated_at_utc")
        elif left_content != right_content:
            raise SplitValidationError(f"Generated file content differs: {relative}")


def manifest_summary(root: Path) -> dict[str, object]:
    manifest = _load_manifest(root.resolve())
    return {
        "deployment_target": manifest.get("deployment_target"),
        "source_commit_sha": manifest.get("source_commit_sha"),
        "file_count": manifest.get("file_count"),
        "content_digest_sha256": manifest.get("content_digest_sha256"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build one deployment repository tree")
    build.add_argument("--repo-root", type=Path, default=Path.cwd())
    build.add_argument("--source-ref", required=True)
    build.add_argument("--target", choices=TARGETS, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--generated-at-utc")
    build.add_argument("--source-repository", default=SOURCE_REPOSITORY)

    validate = subparsers.add_parser("validate", help="Validate a generated deployment tree")
    validate.add_argument("--root", type=Path, required=True)
    validate.add_argument("--target", choices=TARGETS, required=True)
    validate.add_argument("--expected-source-sha")

    compare = subparsers.add_parser("compare", help="Compare two generated trees")
    compare.add_argument("--left", type=Path, required=True)
    compare.add_argument("--right", type=Path, required=True)

    summary = subparsers.add_parser("manifest-summary", help="Print a non-secret manifest summary")
    summary.add_argument("--root", type=Path, required=True)

    workflow = subparsers.add_parser("validate-workflow", help="Require manual-only workflows")
    workflow.add_argument("paths", type=Path, nargs="+")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            manifest = build_repository(
                args.repo_root,
                args.source_ref,
                args.target,
                args.output,
                generated_at_utc=args.generated_at_utc,
                source_repository=args.source_repository,
            )
            result = {
                "deployment_target": manifest["deployment_target"],
                "source_commit_sha": manifest["source_commit_sha"],
                "file_count": manifest["file_count"],
                "content_digest_sha256": manifest["content_digest_sha256"],
                "output": str(args.output.resolve()),
            }
            print(json.dumps(result, sort_keys=True))
        elif args.command == "validate":
            validate_tree(
                args.root,
                args.target,
                expected_source_sha=args.expected_source_sha,
            )
            print(json.dumps(manifest_summary(args.root), sort_keys=True))
        elif args.command == "compare":
            compare_trees(args.left, args.right)
            print("Generated trees are deterministic (excluding generated_at_utc).")
        elif args.command == "manifest-summary":
            print(json.dumps(manifest_summary(args.root), sort_keys=True))
        elif args.command == "validate-workflow":
            for path in args.paths:
                validate_manual_only_workflow(path)
            print(f"Validated {len(args.paths)} manual-only workflow(s).")
        return 0
    except SplitValidationError as exc:
        parser.exit(2, f"deployment split validation failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
