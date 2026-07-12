from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies.auth import require_authenticated_user
from apps.api.dependencies.models import CurrentUser
from apps.api.schemas.users import CurrentUserResponse

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/me", response_model=CurrentUserResponse)
def me(current_user: CurrentUser = Depends(require_authenticated_user)) -> dict[str, object]:
    return {
        "user_uuid": current_user.user_uuid,
        "username": current_user.username,
        "role": current_user.role,
        "account_status": current_user.account_status,
        "created_at": current_user.created_at,
        "activated_at": current_user.activated_at,
        "expires_at": current_user.expires_at,
        "remaining_days": current_user.remaining_days,
        "last_successful_pipeline_run_uuid": current_user.last_successful_pipeline_run_uuid,
        "is_demo": current_user.is_demo,
    }
