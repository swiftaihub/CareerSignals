from __future__ import annotations

import os
import re

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    source_commit_sha = os.getenv("CAREERSIGNAL_SOURCE_COMMIT_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit_sha):
        source_commit_sha = "unknown"
    return {"status": "ok", "source_commit_sha": source_commit_sha}


@router.get("/health", include_in_schema=False)
def root_health() -> dict[str, str]:
    return health()
