from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies.authorization import CurrentUser, require_admin
from apps.api.dependencies.repositories import get_activity_repository
from packages.careersignal_core.repositories.activity import ActivityRepository

router = APIRouter(prefix="/api/admin", tags=["admin-audit"])


@router.get("/audit-logs")
def audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=500),
    action: str | None = Query(default=None, max_length=200),
    _: CurrentUser = Depends(require_admin),
    repository: ActivityRepository = Depends(get_activity_repository),
) -> dict[str, Any]:
    resolved_limit = page_size or limit
    resolved_offset = ((page - 1) * resolved_limit) if page is not None else offset
    total, rows = repository.list_audit_logs(
        limit=resolved_limit, offset=resolved_offset, action=action
    )
    items = [
        {
            **row,
            "action": row.get("action_name"),
            "details": {"before": row.get("before_state"), "after": row.get("after_state")},
        }
        for row in rows
    ]
    return {
        "items": items,
        "total": total,
        "limit": resolved_limit,
        "offset": resolved_offset,
        "page": page or (resolved_offset // resolved_limit + 1),
        "page_size": resolved_limit,
    }
