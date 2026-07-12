from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from apps.api.dependencies.authorization import CurrentUser, require_admin
from apps.api.dependencies.models import APIError
from apps.api.dependencies.repositories import get_connector_run_repository
from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.errors import ConflictError

router = APIRouter(prefix="/api/admin/connector-runs", tags=["admin-connector-runs"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def enqueue_admin_connector_run(
    _: CurrentUser = Depends(require_admin),
    repository: ConnectorRunRepository = Depends(get_connector_run_repository),
) -> dict[str, Any]:
    try:
        run = repository.create_if_no_active(trigger_type="manual_admin")
    except ConflictError as exc:
        raise APIError(
            409,
            "A global connector refresh is already queued or running.",
            "CONNECTOR_REFRESH_ALREADY_ACTIVE",
        ) from exc
    return {
        "connector_run_uuid": run["connector_run_uuid"],
        "status": run["status"],
        "trigger_type": run["trigger_type"],
        "created_at": run["created_at"],
    }


@router.get("")
def list_admin_connector_runs(
    _: CurrentUser = Depends(require_admin),
    repository: ConnectorRunRepository = Depends(get_connector_run_repository),
) -> dict[str, Any]:
    return {"items": repository.admin_list(limit=20)}
