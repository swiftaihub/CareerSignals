from __future__ import annotations

import pytest

from packages.careersignal_core.storage.motherduck import (
    MotherDuckConfigurationError,
    MotherDuckService,
)
from packages.careersignal_core.storage.schema import SCHEMA_SQL, TABLE_SQL


def test_motherduck_service_uses_careersignal_default_database(monkeypatch) -> None:
    monkeypatch.delenv("MOTHERDUCK_DATABASE", raising=False)
    monkeypatch.setenv("CAREERSIGNAL_DATA_MODE", "local")

    service = MotherDuckService()

    assert service.database == "CareerSignal"
    assert service.get_connection_string() == "md:CareerSignal"


def test_motherduck_service_requires_token_in_motherduck_mode(monkeypatch) -> None:
    monkeypatch.setenv("CAREERSIGNAL_DATA_MODE", "motherduck")
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)

    service = MotherDuckService(database="CareerSignal")

    with pytest.raises(MotherDuckConfigurationError):
        service.get_connection_string()


def test_schema_sql_contains_required_schemas_and_tables() -> None:
    schema_sql = "\n".join(SCHEMA_SQL).casefold()
    table_sql = "\n".join(TABLE_SQL).casefold()

    for schema_name in ("raw", "staging", "intermediate", "mart", "app"):
        assert f"create schema if not exists {schema_name}" in schema_sql

    for table_name in (
        "raw.ingestion_runs",
        "raw.job_posts_raw",
        "raw.connector_errors",
        "staging.python_jobs_processed",
        "app.job_application_status",
    ):
        assert table_name in table_sql
