from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from apps.api.config import limiter
from apps.api.dependencies.models import APIError, CurrentUser
from apps.api.dependencies.authorization import require_active_user
from apps.api.dependencies.repositories import (
    get_bootstrap_repository,
    get_config_repository,
    get_connector_run_repository,
    get_pipeline_run_repository,
)
from apps.api.schemas.pipeline import PipelineQuotaResponse, PipelineRunSubmission
from packages.careersignal_core.repositories.bootstrap import BootstrapRepository
from packages.careersignal_core.repositories.configs import ConfigRepository
from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository
from packages.careersignal_core.repositories.errors import (
    ConflictError,
    InvalidStateTransitionError,
    PipelineAlreadyActiveError,
    PipelineDailyLimitError,
)
from packages.careersignal_core.repositories.pipeline_runs import PipelineRunRepository
from packages.careersignal_core.settings import AppSettings, get_settings

router = APIRouter(prefix="/api/pipeline-runs", tags=["pipeline"])


def _pipeline_user(current_user: CurrentUser) -> CurrentUser:
    if current_user.is_demo:
        raise APIError(403, "The Demo pipeline is disabled.", "DEMO_PIPELINE_DISABLED")
    return current_user


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=PipelineRunSubmission)
@limiter.limit("10/hour")
def submit_pipeline_run(
    request: Request,
    response: Response,
    current_user: CurrentUser = Depends(require_active_user),
    configs: ConfigRepository = Depends(get_config_repository),
    runs: PipelineRunRepository = Depends(get_pipeline_run_repository),
    connector_runs: ConnectorRunRepository = Depends(get_connector_run_repository),
    bootstrap: BootstrapRepository = Depends(get_bootstrap_repository),
    settings: AppSettings = Depends(get_settings),
) -> dict[str, Any]:
    current_user = _pipeline_user(current_user)
    snapshot = configs.snapshot(current_user.user_uuid)
    try:
        if not bootstrap.is_completed(current_user.user_uuid):
            created = bootstrap.start_or_get(
                user_uuid=current_user.user_uuid,
                snapshot=snapshot,
                daily_limit=settings.user_pipeline_daily_limit,
            )
            return {
                key: created.get(key)
                for key in (
                    "run_uuid",
                    "status",
                    "submitted_at",
                    "config_hash",
                    "source_connector_run_uuid",
                    "is_bootstrap_run",
                    "bootstrap_status",
                )
            }
        latest_shared = connector_runs.latest_successful()
        if latest_shared is None:
            raise ConflictError("No successful shared data refresh is available yet")
        created = runs.create(
            user_uuid=current_user.user_uuid,
            snapshot=snapshot,
            daily_limit=settings.user_pipeline_daily_limit,
            source_connector_run_uuid=latest_shared["connector_run_uuid"],
        )
        return {
            key: created.get(key)
            for key in (
                "run_uuid",
                "status",
                "submitted_at",
                "config_hash",
                "source_connector_run_uuid",
                "is_bootstrap_run",
            )
        }
    except ConflictError as exc:
        raise APIError(409, str(exc), exc.error_code) from exc
    except PipelineAlreadyActiveError as exc:
        raise APIError(409, "A pipeline run is already queued or running.", exc.error_code) from exc
    except PipelineDailyLimitError as exc:
        raise APIError(429, "Your daily pipeline limit has been reached.", exc.error_code) from exc


@router.get("")
def list_pipeline_runs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_active_user),
    repository: PipelineRunRepository = Depends(get_pipeline_run_repository),
) -> list[dict[str, Any]]:
    return repository.list_for_user(current_user.user_uuid, limit=limit, offset=offset)


@router.get("/quota", response_model=PipelineQuotaResponse)
def get_pipeline_quota(
    current_user: CurrentUser = Depends(require_active_user),
    repository: PipelineRunRepository = Depends(get_pipeline_run_repository),
    settings: AppSettings = Depends(get_settings),
) -> dict[str, Any]:
    return repository.quota_for_user(
        current_user.user_uuid,
        daily_limit=settings.user_pipeline_daily_limit,
    )


@router.get("/{run_uuid}")
def get_pipeline_run(
    run_uuid: UUID,
    current_user: CurrentUser = Depends(require_active_user),
    repository: PipelineRunRepository = Depends(get_pipeline_run_repository),
) -> dict[str, Any]:
    run = repository.get_for_user(current_user.user_uuid, run_uuid)
    if run is None:
        raise APIError(404, "Pipeline run was not found.", "PIPELINE_RUN_NOT_FOUND")
    return run


@router.post("/{run_uuid}/cancel")
def cancel_pipeline_run(
    run_uuid: UUID,
    current_user: CurrentUser = Depends(require_active_user),
    repository: PipelineRunRepository = Depends(get_pipeline_run_repository),
) -> dict[str, Any]:
    _pipeline_user(current_user)
    try:
        return repository.cancel_queued(current_user.user_uuid, run_uuid)
    except InvalidStateTransitionError as exc:
        raise APIError(409, str(exc), exc.error_code) from exc
