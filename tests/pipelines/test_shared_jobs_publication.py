from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from packages.careersignal_core.publication.shared_jobs import (
    SharedJobsPublisher,
    _bounded_optional_timestamp,
    _finite_optional_number,
)


RUN_UUID = "11111111-1111-4111-8111-111111111111"


class _Connection:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.statements: list[str] = []
        self.params: list[list[object]] = []

    def execute(self, statement: str, params=None):
        normalized = " ".join(statement.casefold().split())
        self.statements.append(normalized)
        self.params.append(list(params or []))
        if self.fail_on and self.fail_on in normalized:
            raise RuntimeError("forced publication failure")


class _Store:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self):
        yield self.connection


class _Analytics:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def record_global_snapshot(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def _job() -> dict[str, object]:
    return {
        "job_id": "shared-job-1",
        "source_name": "greenhouse",
        "title": "Analytics Engineer",
        "first_seen_at": "2026-07-12T10:00:00Z",
        "last_seen_at": "2026-07-12T10:00:00Z",
    }


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), "invalid"])
def test_non_finite_shared_salary_values_become_database_null(value: object) -> None:
    assert _finite_optional_number(value) is None


def test_finite_shared_salary_value_is_preserved() -> None:
    assert _finite_optional_number(125000) == 125000


def test_shared_timestamp_normalization_discards_out_of_range_values() -> None:
    assert _bounded_optional_timestamp("48113-11-21T00:00:01Z") is None
    assert _bounded_optional_timestamp("not-a-date") is None
    assert _bounded_optional_timestamp("2026-07-12T10:00:00Z") == datetime(
        2026, 7, 12, 10, 0, tzinfo=timezone.utc
    )


def test_shared_publication_writes_invalid_posted_at_as_database_null() -> None:
    connection = _Connection()
    job = _job()
    job["posted_at"] = "48113-11-21T00:00:01Z"

    SharedJobsPublisher(
        store=_Store(connection),  # type: ignore[arg-type]
        analytics_repository=_Analytics(),  # type: ignore[arg-type]
    ).publish([job], connector_run_uuid=RUN_UUID)

    assert connection.params[0][14] is None


def test_successful_shared_publication_records_snapshot_in_same_transaction() -> None:
    connection = _Connection()
    analytics = _Analytics()

    published = SharedJobsPublisher(
        store=_Store(connection),  # type: ignore[arg-type]
        analytics_repository=analytics,  # type: ignore[arg-type]
    ).publish([_job()], connector_run_uuid=RUN_UUID)

    assert published == 1
    assert analytics.calls == [
        {"connector_run_uuid": RUN_UUID, "connection": connection}
    ]
    assert "update public.job_postings set is_active = false" in connection.statements[-1]
    assert "source_name <> 'demo_seed'" in connection.statements[-1]


def test_failed_shared_publication_does_not_record_snapshot() -> None:
    connection = _Connection(fail_on="insert into public.job_postings")
    analytics = _Analytics()

    with pytest.raises(RuntimeError, match="forced publication failure"):
        SharedJobsPublisher(
            store=_Store(connection),  # type: ignore[arg-type]
            analytics_repository=analytics,  # type: ignore[arg-type]
        ).publish([_job()], connector_run_uuid=RUN_UUID)

    assert analytics.calls == []
