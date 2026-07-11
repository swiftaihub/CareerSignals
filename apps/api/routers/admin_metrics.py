from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies.authorization import CurrentUser, require_admin
from apps.api.dependencies.repositories import get_admin_repository
from packages.careersignal_core.repositories.admin import AdminRepository

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics")
def admin_metrics(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    timezone: str = Query(default="UTC", max_length=64, pattern=r"^[A-Za-z0-9_+\-/]+$"),
    _: CurrentUser = Depends(require_admin),
    repository: AdminRepository = Depends(get_admin_repository),
) -> dict[str, Any]:
    if start_date > end_date:
        from apps.api.dependencies.models import APIError

        raise APIError(400, "start_date must be on or before end_date.", "INVALID_DATE_RANGE")
    return repository.metrics(start_date=start_date, end_date=end_date, timezone=timezone)
