from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends

from apps.api.dependencies.auth import get_current_identity
from apps.api.dependencies.models import APIError, CurrentUser


def require_active_user(
    current_user: CurrentUser = Depends(get_current_identity),
) -> CurrentUser:
    status = current_user.account_status
    if status == "pending":
        raise APIError(403, "Your account is pending activation.", "ACCOUNT_PENDING")
    if status == "suspended":
        raise APIError(403, "Your account is suspended.", "ACCOUNT_SUSPENDED")
    if status == "deleted":
        raise APIError(403, "Your account is unavailable.", "ACCOUNT_DELETED")
    if status != "active":
        raise APIError(403, "Your account is not active.", "ACCOUNT_INACTIVE")
    if current_user.role in {"admin", "demo"}:
        return current_user
    now = datetime.now(timezone.utc)
    expires_at = current_user.expires_at
    if status == "expired" or (expires_at is not None and expires_at <= now):
        raise APIError(403, "Your CareerSignals access has expired.", "ACCOUNT_EXPIRED")
    return current_user


def require_non_demo_user(
    current_user: CurrentUser = Depends(require_active_user),
) -> CurrentUser:
    if current_user.is_demo:
        raise APIError(403, "Demo data is read-only.", "DEMO_READ_ONLY")
    return current_user


def require_admin(
    current_user: CurrentUser = Depends(require_active_user),
) -> CurrentUser:
    if current_user.role != "admin":
        raise APIError(403, "Administrator access is required.", "ADMIN_REQUIRED")
    return current_user
