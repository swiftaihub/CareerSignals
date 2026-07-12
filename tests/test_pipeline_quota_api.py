from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.dependencies.authorization import require_active_user
from apps.api.dependencies.models import CurrentUser
from apps.api.dependencies.repositories import get_pipeline_run_repository
from apps.api.main import app
from packages.careersignal_core.settings import AppSettings, get_settings


USER_UUID = UUID("11111111-1111-4111-8111-111111111111")


def _current_user() -> CurrentUser:
    return CurrentUser(
        user_uuid=USER_UUID,
        username="quota-test",
        role="user",
        account_status="active",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )


class FakePipelineRuns:
    def quota_for_user(self, user_uuid: UUID, *, daily_limit: int | None) -> dict[str, object]:
        assert user_uuid == USER_UUID
        assert daily_limit == 2
        return {
            "limit": 2,
            "used": 1,
            "remaining": 1,
            "window_start": "2026-07-12T00:00:00Z",
            "window_end": "2026-07-13T00:00:00Z",
            "resets_at": "2026-07-13T00:00:00Z",
        }


def test_pipeline_quota_endpoint_is_authenticated_and_reports_successful_usage() -> None:
    app.dependency_overrides[require_active_user] = _current_user
    app.dependency_overrides[get_pipeline_run_repository] = FakePipelineRuns
    app.dependency_overrides[get_settings] = lambda: AppSettings(
        USER_PIPELINE_DAILY_LIMIT=2,
    )
    try:
        response = TestClient(app).get("/api/pipeline-runs/quota")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "limit": 2,
        "used": 1,
        "remaining": 1,
        "window_start": "2026-07-12T00:00:00Z",
        "window_end": "2026-07-13T00:00:00Z",
        "resets_at": "2026-07-13T00:00:00Z",
    }
