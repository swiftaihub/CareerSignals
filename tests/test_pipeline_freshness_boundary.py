from __future__ import annotations

from pathlib import Path
from typing import Any

from src import main as pipeline_main


class FakeMotherDuckService:
    pass


class CapturingIngestionWriter:
    raw_rows_written = -1

    def __init__(self, service: FakeMotherDuckService) -> None:
        self.service = service

    def start_run(self, run_id: str, data_mode: str) -> None:
        pass

    def write_raw_jobs(
        self,
        run_id: str,
        raw_records: list[dict[str, Any]],
        progress: Any | None = None,
    ) -> int:
        self.__class__.raw_rows_written = len(raw_records)
        return len(raw_records)

    def write_connector_errors(self, run_id: str, errors: list[dict[str, Any]]) -> int:
        return len(errors)

    def write_candidate_skills(self, candidate: Any) -> int:
        return 0

    def write_processed_jobs(
        self,
        run_id: str,
        jobs: list[dict[str, Any]],
        progress: Any | None = None,
    ) -> int:
        return len(jobs)

    def complete_run(self, **kwargs: Any) -> None:
        pass

    def fail_run(self, run_id: str, error_message: str) -> None:
        pass


def test_motherduck_raw_write_happens_after_freshness_filter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CAREERSIGNAL_DATA_MODE", "motherduck")
    monkeypatch.setenv("JOB_SOURCES", "mock")
    monkeypatch.setenv("CAREERSIGNAL_RUN_DBT", "false")
    monkeypatch.setenv("CAREERSIGNAL_RUN_DBT_TESTS", "false")
    monkeypatch.setenv("CAREERSIGNAL_WRITE_DEBUG_JSON", "false")
    monkeypatch.setenv("CAREERSIGNAL_EXCEL_PATH", str(tmp_path / "tracker.xlsx"))
    monkeypatch.setattr(pipeline_main, "MotherDuckService", FakeMotherDuckService)
    monkeypatch.setattr(pipeline_main, "MotherDuckIngestionWriter", CapturingIngestionWriter)
    monkeypatch.setattr(pipeline_main, "init_motherduck_schema", lambda service: None)

    summary = pipeline_main.run_pipeline(Path.cwd())

    assert summary["fetched_raw_jobs"] == 15
    assert summary["raw_jobs"] == 0
    assert summary["freshness_filtered_out"] == 15
    assert summary["excel_exported"] is False
    assert summary["output_path"] is None
    assert CapturingIngestionWriter.raw_rows_written == 0
    assert not list(tmp_path.glob("*.xlsx"))
