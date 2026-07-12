from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies.authorization import CurrentUser, require_active_user
from apps.api.dependencies.repositories import get_connector_run_repository
from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.scheduling import get_next_connector_refresh_at
from packages.careersignal_core.settings import AppSettings, get_settings

router = APIRouter(prefix="/api", tags=["freshness"])


@router.get("/data-freshness")
def data_freshness(
    _: CurrentUser = Depends(require_active_user),
    repository: ConnectorRunRepository = Depends(get_connector_run_repository),
    settings: AppSettings = Depends(get_settings),
) -> dict[str, Any]:
    result = repository.freshness(stale_after_hours=settings.connector_stale_after_hours)
    result["overall"]["next_scheduled_refresh_at"] = get_next_connector_refresh_at(settings)
    return result
