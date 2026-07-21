from __future__ import annotations

from contextlib import contextmanager

import duckdb
import pytest

from packages.careersignal_core.storage.ingestion import MotherDuckIngestionWriter
from packages.careersignal_core.storage.motherduck import (
    MotherDuckConfigurationError,
    MotherDuckService,
)
from packages.careersignal_core.storage.schema import (
    MIGRATION_SQL,
    SCHEMA_SQL,
    TABLE_SQL,
    init_motherduck_schema,
)


class LocalDuckDbService:
    def __init__(self, path) -> None:
        self.path = str(path)

    @contextmanager
    def connect(self):
        connection = duckdb.connect(self.path)
        try:
            yield connection
        finally:
            connection.close()


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
    migration_sql = "\n".join(MIGRATION_SQL).casefold()

    for schema_name in ("raw", "staging", "intermediate", "mart", "app"):
        assert f"create schema if not exists {schema_name}" in schema_sql

    for table_name in (
        "raw.ingestion_runs",
        "raw.job_posts_raw",
        "raw.connector_errors",
        "raw.greenhouse_job_state",
        "staging.python_jobs_processed",
        "app.job_application_status",
    ):
        assert table_name in table_sql

    for column_name in (
        "location_normalized",
        "location_group",
        "visa_status",
        "visa_evidence",
        "visa_confidence",
    ):
        assert column_name in table_sql
        assert column_name in migration_sql


def test_greenhouse_job_state_round_trips_without_board_token(tmp_path) -> None:
    service = LocalDuckDbService(tmp_path / "state.duckdb")
    init_motherduck_schema(service)  # type: ignore[arg-type]
    writer = MotherDuckIngestionWriter(service)  # type: ignore[arg-type]

    written = writer.write_greenhouse_job_state(
        [
            {
                "board_key": "board-hash",
                "job_post_id": "123",
                "upstream_updated_at": "2026-07-09T10:00:00Z",
                "first_published_at": "2026-07-09T09:00:00Z",
                "detail_payload": {
                    "id": 123,
                    "title": "Analytics Engineer",
                    "content": "Build reliable data systems.",
                },
            }
        ]
    )
    loaded = writer.load_greenhouse_job_state()

    assert written == 1
    assert loaded[("board-hash", "123")]["first_published_at"] == (
        "2026-07-09T09:00:00Z"
    )
    assert loaded[("board-hash", "123")]["detail_payload"]["title"] == (
        "Analytics Engineer"
    )
    assert "company-token" not in repr(loaded)
