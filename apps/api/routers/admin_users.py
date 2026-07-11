from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status

from apps.api.config import limiter
from apps.api.dependencies.authorization import CurrentUser, require_admin
from apps.api.dependencies.models import APIError
from apps.api.dependencies.repositories import get_admin_repository, get_user_repository
from apps.api.schemas.admin import (
    AdminCreateUserRequest,
    AdminNoteRequest,
    AdminUpdateUserRequest,
    EntitlementAdjustmentRequest,
)
from apps.api.services.admin_service import AdminService
from packages.careersignal_core.repositories.admin import AdminRepository
from packages.careersignal_core.repositories.users import UserRepository

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


@router.get("")
def list_users(
    search: str | None = Query(default=None, max_length=320),
    user_uuid: UUID | None = Query(default=None),
    username: str | None = Query(default=None, max_length=32),
    email: str | None = Query(default=None, max_length=320),
    account_status: str | None = None,
    role: str | None = None,
    created_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    created_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    expires_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    expires_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=200),
    _: CurrentUser = Depends(require_admin),
    repository: AdminRepository = Depends(get_admin_repository),
) -> dict[str, Any]:
    resolved_limit = page_size or limit
    resolved_offset = ((page - 1) * resolved_limit) if page is not None else offset
    total, items = repository.list_users(
        search=search,
        user_uuid=str(user_uuid) if user_uuid else None,
        username=username,
        email=email,
        account_status=account_status,
        role=role,
        created_from=created_from,
        created_to=created_to,
        expires_from=expires_from,
        expires_to=expires_to,
        limit=resolved_limit,
        offset=resolved_offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": resolved_limit,
        "offset": resolved_offset,
        "page": page or (resolved_offset // resolved_limit + 1),
        "page_size": resolved_limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/hour")
def create_user(
    request: Request,
    response: Response,
    payload: AdminCreateUserRequest,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    profile = AdminService().create_user(
        admin=admin,
        username=payload.username,
        email=str(payload.email),
        temporary_password=payload.temporary_password,
        require_password_change=payload.require_password_change,
        request=request,
    )
    profile.pop("auth_user_id", None)
    return profile


@router.get("/{user_uuid}")
def get_user(
    user_uuid: UUID,
    _: CurrentUser = Depends(require_admin),
    repository: UserRepository = Depends(get_user_repository),
) -> dict[str, Any]:
    profile = repository.get_by_user_uuid(user_uuid, include_deleted=True)
    if profile is None:
        raise APIError(404, "User was not found.", "USER_NOT_FOUND")
    profile.pop("auth_user_id", None)
    return profile


@router.patch("/{user_uuid}")
def update_user(
    user_uuid: UUID,
    payload: AdminUpdateUserRequest,
    request: Request,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    return AdminService().update_user(
        admin=admin,
        target_user_uuid=user_uuid,
        username=payload.username,
        email=str(payload.email) if payload.email else None,
        request=request,
    )


@router.post("/{user_uuid}/activate")
def activate_user(
    user_uuid: UUID,
    request: Request,
    payload: AdminNoteRequest = AdminNoteRequest(),
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    return AdminService().activate(
        admin=admin, target_user_uuid=user_uuid, note=payload.note, request=request
    )


@router.post("/{user_uuid}/expire")
def expire_user(
    user_uuid: UUID,
    request: Request,
    payload: AdminNoteRequest = AdminNoteRequest(),
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    return AdminService().expire(
        admin=admin, target_user_uuid=user_uuid, note=payload.note, request=request
    )


@router.post("/{user_uuid}/grant-days")
def grant_days(
    user_uuid: UUID,
    payload: EntitlementAdjustmentRequest,
    request: Request,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    return AdminService().adjust_days(
        admin=admin,
        target_user_uuid=user_uuid,
        days_delta=payload.days,
        note=payload.note,
        request=request,
    )


@router.post("/{user_uuid}/reduce-days")
def reduce_days(
    user_uuid: UUID,
    payload: EntitlementAdjustmentRequest,
    request: Request,
    admin: CurrentUser = Depends(require_admin),
) -> dict[str, Any]:
    return AdminService().adjust_days(
        admin=admin,
        target_user_uuid=user_uuid,
        days_delta=-payload.days,
        note=payload.note,
        request=request,
    )


@router.post("/{user_uuid}/suspend")
def suspend_user(
    user_uuid: UUID, request: Request, admin: CurrentUser = Depends(require_admin)
) -> dict[str, Any]:
    return AdminService().suspend(admin=admin, target_user_uuid=user_uuid, request=request)


@router.post("/{user_uuid}/restore")
def restore_user(
    user_uuid: UUID, request: Request, admin: CurrentUser = Depends(require_admin)
) -> dict[str, Any]:
    return AdminService().restore(admin=admin, target_user_uuid=user_uuid, request=request)


@router.post("/{user_uuid}/reset-password")
def reset_password(
    user_uuid: UUID, request: Request, admin: CurrentUser = Depends(require_admin)
) -> dict[str, str]:
    return AdminService().reset_password(admin=admin, target_user_uuid=user_uuid, request=request)


@router.post("/{user_uuid}/revoke-sessions")
def revoke_sessions(
    user_uuid: UUID, request: Request, admin: CurrentUser = Depends(require_admin)
) -> dict[str, str]:
    return AdminService().revoke_sessions(admin=admin, target_user_uuid=user_uuid, request=request)


@router.delete("/{user_uuid}")
def delete_user(
    user_uuid: UUID, request: Request, admin: CurrentUser = Depends(require_admin)
) -> dict[str, Any]:
    return AdminService().soft_delete(admin=admin, target_user_uuid=user_uuid, request=request)
