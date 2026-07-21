from __future__ import annotations

import logging
import threading
import time

from src.config.schemas import ConnectorRetryConfig, JobCategoryConfig
from src.pipelines.shared_connector_refresh import (
    _compact_connector_records,
    _source_results,
    collect_connector_jobs,
)


SENSITIVE_EXCEPTION_TEXT = (
    "https://user:password@example.test/jobs?api_key=connector-secret"
)


class FailingConnector:
    source_name = "credentialed-source"

    def fetch_jobs(self, category: JobCategoryConfig):
        raise RuntimeError(SENSITIVE_EXCEPTION_TEXT)


class TrackingConnector:
    def __init__(self, source_name: str, state: dict[str, int], lock: threading.Lock) -> None:
        self.source_name = source_name
        self.state = state
        self.lock = lock

    def fetch_jobs(self, category: JobCategoryConfig):
        with self.lock:
            self.state["active"] += 1
            self.state["maximum"] = max(self.state["maximum"], self.state["active"])
        time.sleep(0.04)
        with self.lock:
            self.state["active"] -= 1
        return []


class SuccessfulConnector:
    source_name = "successful-source"

    def fetch_jobs(self, category: JobCategoryConfig):
        return [{"external_id": "record-1"}]


class BulkConnector:
    source_name = "bulk-source"

    def __init__(self) -> None:
        self.calls = 0

    def fetch_jobs_for_categories(self, categories: list[JobCategoryConfig]):
        self.calls += 1
        return [
            {
                "external_id": "record-1",
                "_careersignal_category": categories[0],
            }
        ]


def test_connector_exception_text_is_not_logged_or_persisted(caplog) -> None:
    connector = FailingConnector()
    category = JobCategoryConfig(
        category_name="Analytics",
        search_titles=["Analytics Engineer"],
    )
    caplog.set_level(logging.ERROR, logger="src.pipelines.shared_connector_refresh")

    records, errors = collect_connector_jobs(
        [connector],
        [category],
        retry=ConnectorRetryConfig(max_attempts=1, backoff_seconds=0),
    )
    results = _source_results([connector], records, [], errors)

    assert records == []
    assert errors == [
        {
            "source": "credentialed-source",
            "category_name": "Analytics",
            "query_title": "Analytics Engineer",
            "error_message": "Connector request failed.",
            "error_type": "RuntimeError",
        }
    ]
    assert results[0]["public_status_message"] == "The source refresh failed."
    assert results[0]["internal_error_message"] == (
        "RuntimeError: Connector request failed."
    )
    assert SENSITIVE_EXCEPTION_TEXT not in caplog.text
    assert "connector-secret" not in repr(errors)
    assert "connector-secret" not in repr(results)


def test_connector_sources_are_collected_concurrently() -> None:
    state = {"active": 0, "maximum": 0}
    lock = threading.Lock()
    connectors = [
        TrackingConnector("source-one", state, lock),
        TrackingConnector("source-two", state, lock),
    ]
    category = JobCategoryConfig(
        category_name="Analytics",
        search_titles=["Analytics Engineer"],
    )

    collect_connector_jobs(
        connectors,  # type: ignore[arg-type]
        [category],
        max_source_concurrency=2,
    )

    assert state["maximum"] == 2


def test_connector_source_logs_start_and_completion_without_changing_results(caplog) -> None:
    connector = SuccessfulConnector()
    category = JobCategoryConfig(
        category_name="Analytics",
        search_titles=["Analytics Engineer"],
    )
    caplog.set_level(logging.INFO, logger="src.pipelines.shared_connector_refresh")

    records, errors = collect_connector_jobs(
        [connector],  # type: ignore[list-item]
        [category],
    )

    assert records == [
        {
            "external_id": "record-1",
            "_careersignal_category": category,
            "_careersignal_source": "successful-source",
        }
    ]
    assert errors == []
    assert "Connector successful-source started (categories=1)" in caplog.text
    assert (
        "Connector successful-source completed "
        "(records=1, errors=0, elapsed_seconds="
    ) in caplog.text


def test_bulk_connector_collects_all_categories_in_one_call() -> None:
    connector = BulkConnector()
    categories = [
        JobCategoryConfig(category_name="Analytics"),
        JobCategoryConfig(category_name="Data Science"),
    ]

    records, errors = collect_connector_jobs(
        [connector],  # type: ignore[list-item]
        categories,
    )

    assert connector.calls == 1
    assert errors == []
    assert len(records) == 1
    assert records[0]["_careersignal_category"] == categories[0]


def test_compact_connector_records_keeps_first_category_per_source_job() -> None:
    first_category = JobCategoryConfig(category_name="Analytics")
    second_category = JobCategoryConfig(category_name="Data")
    records = [
        {
            "source": "greenhouse",
            "external_id": "job-1",
            "category_name": "Analytics",
            "_careersignal_category": first_category,
            "_careersignal_source": "greenhouse",
        },
        {
            "source": "greenhouse",
            "external_id": "job-1",
            "category_name": "Data",
            "_careersignal_category": second_category,
            "_careersignal_source": "greenhouse",
        },
    ]

    compacted = _compact_connector_records(records)

    assert compacted == [records[0]]


def test_compact_connector_records_does_not_trust_external_id_across_boards() -> None:
    category = JobCategoryConfig(category_name="Analytics")
    records = [
        {
            "source": "greenhouse",
            "external_id": "123",
            "title": "Data Analyst",
            "company": "Company One",
            "location": "New York",
            "_careersignal_category": category,
        },
        {
            "source": "greenhouse",
            "external_id": "123",
            "title": "Data Analyst",
            "company": "Company Two",
            "location": "New York",
            "_careersignal_category": category,
        },
    ]

    assert _compact_connector_records(records) == records
