from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import Request, Response

from apps.api.dependencies.models import CurrentUser
from apps.api.routers.pipeline_runs import submit_pipeline_run


USER_UUID = UUID("11111111-1111-4111-8111-111111111111")
CONNECTOR_RUN_UUID = UUID("22222222-2222-4222-8222-222222222222")
PIPELINE_RUN_UUID = UUID("33333333-3333-4333-8333-333333333333")
BOOTSTRAP_RUN_UUID = UUID("44444444-4444-4444-8444-444444444444")


def _current_user() -> CurrentUser:
    return CurrentUser(
        user_uuid=USER_UUID,
        username="pipeline-test",
        role="user",
        account_status="active",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )


def _request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/api/pipeline-runs", "headers": []})


class _Configs:
    snapshot_value = {
        "config_hash": "snapshot-hash",
        "config_revision_map": {},
    }

    def snapshot(self, user_uuid: UUID):
        assert user_uuid == USER_UUID
        return self.snapshot_value


class _BootstrapMustNotRun:
    def is_completed(self, _user_uuid: UUID):
        raise AssertionError("scheduled mode must not inspect or start first-user bootstrap")

    def start_or_get(self, **_kwargs):
        raise AssertionError("scheduled mode must not start first-user bootstrap")


class _BootstrapEnabled:
    def __init__(self) -> None:
        self.started = False

    def is_completed(self, user_uuid: UUID):
        assert user_uuid == USER_UUID
        return False

    def start_or_get(self, **kwargs):
        self.started = True
        assert kwargs["user_uuid"] == USER_UUID
        assert kwargs["snapshot"] == _Configs.snapshot_value
        assert kwargs["daily_limit"] == 4
        return {
            "run_uuid": BOOTSTRAP_RUN_UUID,
            "status": "waiting_for_global",
            "submitted_at": datetime(2026, 7, 18, tzinfo=timezone.utc),
            "config_hash": "snapshot-hash",
            "source_connector_run_uuid": None,
            "is_bootstrap_run": True,
            "bootstrap_status": "global_queued",
        }


class _ConnectorRuns:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed

    def latest_successful(self):
        if not self.allowed:
            raise AssertionError("bootstrap mode must not reuse shared data before bootstrap")
        return {"connector_run_uuid": CONNECTOR_RUN_UUID}


class _PipelineRuns:
    def __init__(self, *, allowed: bool) -> None:
        self.allowed = allowed
        self.created = None

    def create(self, **kwargs):
        if not self.allowed:
            raise AssertionError("bootstrap mode must not enqueue a regular personal run")
        self.created = kwargs
        return {
            "run_uuid": PIPELINE_RUN_UUID,
            "status": "queued",
            "submitted_at": datetime(2026, 7, 18, tzinfo=timezone.utc),
            "config_hash": "snapshot-hash",
            "source_connector_run_uuid": CONNECTOR_RUN_UUID,
            "is_bootstrap_run": False,
        }


def _submit(*, mode: str, runs, connector_runs, bootstrap):
    return submit_pipeline_run.__wrapped__(
        request=_request(),
        response=Response(),
        current_user=_current_user(),
        configs=_Configs(),
        runs=runs,
        connector_runs=connector_runs,
        bootstrap=bootstrap,
        settings=SimpleNamespace(
            connector_refresh_trigger_mode=mode,
            user_pipeline_daily_limit=4,
        ),
    )


def test_scheduled_mode_skips_first_user_bootstrap_and_reuses_shared_data() -> None:
    runs = _PipelineRuns(allowed=True)

    result = _submit(
        mode="scheduled",
        runs=runs,
        connector_runs=_ConnectorRuns(allowed=True),
        bootstrap=_BootstrapMustNotRun(),
    )

    assert result["run_uuid"] == PIPELINE_RUN_UUID
    assert result["is_bootstrap_run"] is False
    assert runs.created == {
        "user_uuid": USER_UUID,
        "snapshot": _Configs.snapshot_value,
        "daily_limit": 4,
        "source_connector_run_uuid": CONNECTOR_RUN_UUID,
    }


def test_both_mode_keeps_first_user_bootstrap_available() -> None:
    bootstrap = _BootstrapEnabled()

    result = _submit(
        mode="both",
        runs=_PipelineRuns(allowed=False),
        connector_runs=_ConnectorRuns(allowed=False),
        bootstrap=bootstrap,
    )

    assert bootstrap.started is True
    assert result["run_uuid"] == BOOTSTRAP_RUN_UUID
    assert result["is_bootstrap_run"] is True
    assert result["bootstrap_status"] == "global_queued"
