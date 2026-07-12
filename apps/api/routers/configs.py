from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from apps.api.dependencies.authorization import CurrentUser, require_active_user, require_non_demo_user
from apps.api.dependencies.repositories import get_config_repository
from apps.api.schemas.configs import ConfigUpdateRequest, ResetFieldRequest
from packages.careersignal_core.repositories.configs import ConfigRepository

router = APIRouter(prefix="/api/configs", tags=["configuration"])


@router.get("")
def list_configs(
    current_user: CurrentUser = Depends(require_active_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> list[dict[str, Any]]:
    return repository.list(current_user.user_uuid)


@router.get("/{config_type}")
def get_config(
    config_type: str,
    current_user: CurrentUser = Depends(require_active_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> dict[str, Any]:
    return repository.get(current_user.user_uuid, config_type)


@router.put("/{config_type}")
def update_config(
    config_type: str,
    payload: ConfigUpdateRequest,
    current_user: CurrentUser = Depends(require_non_demo_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> dict[str, Any]:
    return repository.update(
        user_uuid=current_user.user_uuid,
        config_type=config_type,
        override_config=payload.override_config,
        changed_by_user_uuid=current_user.user_uuid,
    )


@router.post("/{config_type}/reset")
def reset_config(
    config_type: str,
    current_user: CurrentUser = Depends(require_non_demo_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> dict[str, Any]:
    return repository.reset(
        user_uuid=current_user.user_uuid,
        config_type=config_type,
        changed_by_user_uuid=current_user.user_uuid,
    )


@router.post("/{config_type}/reset-field")
def reset_config_field(
    config_type: str,
    payload: ResetFieldRequest,
    current_user: CurrentUser = Depends(require_non_demo_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> dict[str, Any]:
    return repository.reset_field(
        user_uuid=current_user.user_uuid,
        config_type=config_type,
        field_path=payload.field_path,
        changed_by_user_uuid=current_user.user_uuid,
    )


@router.get("/{config_type}/versions")
def config_versions(
    config_type: str,
    current_user: CurrentUser = Depends(require_active_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> list[dict[str, Any]]:
    return repository.versions(current_user.user_uuid, config_type)


@router.post("/{config_type}/restore/{revision}")
def restore_config(
    config_type: str,
    revision: int,
    current_user: CurrentUser = Depends(require_non_demo_user),
    repository: ConfigRepository = Depends(get_config_repository),
) -> dict[str, Any]:
    return repository.restore(
        user_uuid=current_user.user_uuid,
        config_type=config_type,
        revision=revision,
        changed_by_user_uuid=current_user.user_uuid,
    )
