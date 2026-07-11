from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health", include_in_schema=False)
def root_health() -> dict[str, str]:
    return health()
