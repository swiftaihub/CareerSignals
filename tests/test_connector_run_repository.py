from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from packages.careersignal_core.repositories.connector_runs import ConnectorRunRepository


class CapturingStore:
    def __init__(self) -> None:
        self.params = None

    def fetch_one(self, statement, params):
        self.params = params
        return {"connector_run_uuid": "11111111-1111-4111-8111-111111111111"}


def test_create_normalizes_scheduled_timestamps_to_utc() -> None:
    store = CapturingStore()
    repository = ConnectorRunRepository(store=store)

    repository.create(
        trigger_type="scheduled",
        scheduled_for=datetime(2026, 7, 11, 7, tzinfo=ZoneInfo("America/New_York")),
        next_scheduled_at=datetime(2026, 7, 11, 16, tzinfo=ZoneInfo("America/New_York")),
    )

    assert store.params[1] == datetime(2026, 7, 11, 11, tzinfo=timezone.utc)
    assert store.params[2] == datetime(2026, 7, 11, 20, tzinfo=timezone.utc)


def test_create_rejects_naive_schedule_timestamp() -> None:
    repository = ConnectorRunRepository(store=CapturingStore())

    with pytest.raises(ValueError, match="scheduled_for must be a timezone-aware datetime"):
        repository.create(
            trigger_type="scheduled",
            scheduled_for=datetime(2026, 7, 11, 7),
        )


def test_create_rejects_unknown_trigger_type() -> None:
    repository = ConnectorRunRepository(store=CapturingStore())

    with pytest.raises(ValueError, match="Unsupported connector refresh trigger_type"):
        repository.create(trigger_type="mystery")
