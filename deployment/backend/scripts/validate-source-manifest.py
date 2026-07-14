#!/usr/bin/env python3
"""Validate immutable source provenance without printing configuration values."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="backend")
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--manifest", type=Path, default=Path("SOURCE_MANIFEST.json"))
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors: list[str] = []
    source_sha = str(manifest.get("source_commit_sha", ""))
    if manifest.get("source_repository") != "swiftaihub/CareerSignals":
        errors.append("unexpected source_repository")
    if manifest.get("deployment_target") != args.target:
        errors.append("unexpected deployment_target")
    if manifest.get("source_branch") != "main":
        errors.append("production deployment requires a canonical main source")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_sha):
        errors.append("source_commit_sha must be a full Git SHA")
    if not re.fullmatch(r"[0-9a-f]{40}", args.expected_sha):
        errors.append("expected source SHA must be a full lowercase Git SHA")
    if source_sha.lower() != args.expected_sha.lower():
        errors.append("source_commit_sha does not match the manually confirmed SHA")
    try:
        datetime.fromisoformat(str(manifest.get("generated_at_utc", "")).replace("Z", "+00:00"))
    except ValueError:
        errors.append("generated_at_utc is invalid")

    if errors:
        for error in errors:
            print(f"Manifest validation failed: {error}")
        return 1
    print(f"Validated {args.target} source manifest for {source_sha}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
