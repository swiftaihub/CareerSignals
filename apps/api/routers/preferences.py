from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response

from apps.api.config import limiter
from apps.api.dependencies.authorization import CurrentUser, require_active_user, require_non_demo_user
from apps.api.dependencies.models import APIError
from apps.api.dependencies.preferences import get_preferences_service
from apps.api.schemas.preferences import (
    PreferenceOptionKind,
    PreferencesDocument,
    PreferencesEditableRequest,
    PreferencesMutationRequest,
    PreferencesOptionsResponse,
    PreferencesPreviewResponse,
    PreferencesUpdateRequest,
    RevisionHistoryItem,
)
from packages.careersignal_core.preferences.compiler import PreferencesCompileError
from packages.careersignal_core.preferences.service import PreferencesService


router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("", response_model=PreferencesDocument)
def get_preferences(
    current_user: CurrentUser = Depends(require_active_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> PreferencesDocument:
    return service.get_preferences(current_user.user_uuid)


@router.get("/options", response_model=PreferencesOptionsResponse)
def get_preference_options(
    kind: PreferenceOptionKind | None = Query(default=None),
    q: str = Query(default="", max_length=160),
    limit: int = Query(default=25, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    _: CurrentUser = Depends(require_active_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> dict[str, Any]:
    try:
        return service.options(kind=kind, query=q, limit=limit, offset=offset)
    except ValueError as exc:
        raise APIError(400, str(exc), "INVALID_PREFERENCE_OPTION") from exc


@router.post("/preview", response_model=PreferencesPreviewResponse)
@limiter.limit("30/hour")
def preview_preferences(
    request: Request,
    response: Response,
    payload: PreferencesEditableRequest,
    current_user: CurrentUser = Depends(require_active_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> dict[str, Any]:
    try:
        preview = service.preview(current_user.user_uuid, payload.to_payload())
    except PreferencesCompileError as exc:
        raise APIError(422, str(exc), "INVALID_PREFERENCES") from exc
    return {
        "generated_preview": preview.generated_preview.model_dump(mode="json"),
        "derived_candidate_profile": preview.generated_preview.derived_candidate_profile,
        "warnings": preview.warnings,
        "profile_completeness": preview.profile_completeness,
    }


@router.put("", response_model=PreferencesDocument)
@limiter.limit("30/hour")
def update_preferences(
    request: Request,
    response: Response,
    payload: PreferencesUpdateRequest,
    current_user: CurrentUser = Depends(require_non_demo_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> PreferencesDocument:
    try:
        return service.save_preferences(
            current_user.user_uuid,
            payload.to_payload(),
            changed_by_user_uuid=current_user.user_uuid,
            expected_bundle_revision_uuid=payload.expected_bundle_revision_uuid,
            expected_revision=payload.expected_revision,
            source_ui_version=payload.source_ui_version,
        )
    except PreferencesCompileError as exc:
        raise APIError(422, str(exc), "INVALID_PREFERENCES") from exc


@router.get("/history", response_model=list[RevisionHistoryItem])
def get_preferences_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = Depends(require_active_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> list[RevisionHistoryItem]:
    return service.list_history(current_user.user_uuid, limit=limit, offset=offset)


@router.post("/history/{revision_identifier}/restore", response_model=PreferencesDocument)
def restore_preferences(
    revision_identifier: str,
    payload: PreferencesMutationRequest | None = None,
    current_user: CurrentUser = Depends(require_non_demo_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> PreferencesDocument:
    # The canonical frontend path accepts either the bundle UUID or its numeric
    # display revision for backward-compatible history links.
    if payload and (payload.expected_bundle_revision_uuid is not None or payload.expected_revision is not None):
        state = service.repository.load_current(current_user.user_uuid)
        service._expected_revision(
            state,
            expected_bundle_revision_uuid=payload.expected_bundle_revision_uuid,
            expected_revision=payload.expected_revision,
        )
    return service.restore_identifier(
        current_user.user_uuid,
        revision_identifier,
        changed_by_user_uuid=current_user.user_uuid,
    )


@router.post("/reset", response_model=PreferencesDocument)
def reset_preferences(
    payload: PreferencesMutationRequest | None = None,
    current_user: CurrentUser = Depends(require_non_demo_user),
    service: PreferencesService = Depends(get_preferences_service),
) -> PreferencesDocument:
    payload = payload or PreferencesMutationRequest()
    return service.reset(
        current_user.user_uuid,
        changed_by_user_uuid=current_user.user_uuid,
        expected_bundle_revision_uuid=payload.expected_bundle_revision_uuid,
        expected_revision=payload.expected_revision,
    )
