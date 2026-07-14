from __future__ import annotations

import logging

from src.config.schemas import ConnectorRetryConfig, JobCategoryConfig
from src.pipelines.shared_connector_refresh import _source_results, collect_connector_jobs


SENSITIVE_EXCEPTION_TEXT = (
    "https://user:password@example.test/jobs?api_key=connector-secret"
)


class FailingConnector:
    source_name = "credentialed-source"

    def fetch_jobs(self, category: JobCategoryConfig):
        raise RuntimeError(SENSITIVE_EXCEPTION_TEXT)


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
