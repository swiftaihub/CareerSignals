from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient

from apps.api.dependencies.authorization import require_admin
from apps.api.dependencies.models import CurrentUser
from apps.api.dependencies.repositories import get_connector_run_repository
from apps.api.main import app
from packages.careersignal_core.repositories.errors import ConflictError


ADMIN_USER = CurrentUser(
    user_uuid=UUID("11111111-1111-4111-8111-111111111111"),
    username="admin",
    role="admin",
    account_status="active",
    created_at=datetime.now(timezone.utc),
    activated_at=datetime.now(timezone.utc),
    expires_at=None,
    remaining_days=None,
    last_successful_pipeline_run_uuid=None,
)


class FakeConnectorRunRepository:
    def __init__(self, *, conflict: bool = False) -> None:
        self.conflict = conflict
        self.created: list[str] = []

    def create_if_no_active(self, *, trigger_type: str):
        if self.conflict:
            raise ConflictError("active")
        self.created.append(trigger_type)
        return {
            "connector_run_uuid": "33333333-3333-4333-8333-333333333333",
            "status": "queued",
            "trigger_type": trigger_type,
            "created_at": "2026-07-12T12:00:00Z",
        }

    def admin_list(self, *, limit: int = 20):
        return []


def test_admin_can_enqueue_manual_global_refresh() -> None:
    repository = FakeConnectorRunRepository()
    app.dependency_overrides[require_admin] = lambda: ADMIN_USER
    app.dependency_overrides[get_connector_run_repository] = lambda: repository
    client = TestClient(app)

    response = client.post("/api/admin/connector-runs")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert repository.created == ["manual_admin"]
    assert response.json()["trigger_type"] == "manual_admin"


def test_admin_manual_global_refresh_rejects_overlap() -> None:
    app.dependency_overrides[require_admin] = lambda: ADMIN_USER
    app.dependency_overrides[get_connector_run_repository] = lambda: FakeConnectorRunRepository(conflict=True)
    client = TestClient(app)

    response = client.post("/api/admin/connector-runs")

    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["error_code"] == "CONNECTOR_REFRESH_ALREADY_ACTIVE"
