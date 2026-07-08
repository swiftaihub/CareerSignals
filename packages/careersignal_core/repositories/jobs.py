"""Job repository abstraction for local and MotherDuck modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from packages.careersignal_core.settings import data_mode, excel_path
from packages.careersignal_core.storage.motherduck import MotherDuckService


@dataclass(frozen=True)
class JobFilters:
    limit: int = 100
    offset: int = 0
    category_name: str | None = None
    min_match_score: float | None = None


@dataclass(frozen=True)
class PaginatedJobs:
    total: int
    items: list[dict[str, Any]]


class JobRepository(ABC):
    @abstractmethod
    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        raise NotImplementedError

    @abstractmethod
    def get_top_matches(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_category_summary(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_skill_gap(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_company_priority(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_status(self) -> dict[str, Any]:
        raise NotImplementedError


def _records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []
    clean = dataframe.where(pd.notna(dataframe), None)
    return clean.to_dict(orient="records")


class LocalJobRepository(JobRepository):
    """Reads latest local Excel workbook as a fallback data source."""

    def __init__(self, workbook_path: str | Path | None = None) -> None:
        self.workbook_path = self._resolve_workbook_path(Path(workbook_path or excel_path()))

    def _resolve_workbook_path(self, configured_path: Path) -> Path:
        if configured_path.exists():
            return configured_path

        output_dir = configured_path.parent
        timestamped_pattern = f"{configured_path.stem}_*.xlsx"
        candidates = sorted(
            output_dir.glob(timestamped_pattern),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]

        return configured_path

    def _sheet(self, name: str) -> pd.DataFrame:
        if not self.workbook_path.exists():
            return pd.DataFrame()
        try:
            return pd.read_excel(self.workbook_path, sheet_name=name)
        except ValueError:
            return pd.DataFrame()

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        dataframe = self._sheet("All Jobs")
        if dataframe.empty:
            return PaginatedJobs(total=0, items=[])
        if filters.category_name and "Category" in dataframe:
            dataframe = dataframe[dataframe["Category"] == filters.category_name]
        if filters.min_match_score is not None and "Match Score" in dataframe:
            dataframe = dataframe[dataframe["Match Score"] >= filters.min_match_score]
        total = len(dataframe)
        page = dataframe.iloc[filters.offset : filters.offset + filters.limit]
        return PaginatedJobs(total=total, items=_records(page))

    def get_top_matches(self) -> list[dict[str, Any]]:
        return _records(self._sheet("Top Matches"))

    def get_category_summary(self) -> list[dict[str, Any]]:
        return _records(self._sheet("By Category Summary"))

    def get_skill_gap(self) -> list[dict[str, Any]]:
        return _records(self._sheet("Skill Gap Analysis"))

    def get_company_priority(self) -> list[dict[str, Any]]:
        return _records(self._sheet("Company Priority List"))

    def get_status(self) -> dict[str, Any]:
        return {
            "data_mode": "local",
            "database": "Local",
            "last_pipeline_run": None,
            "last_dbt_run": None,
            "mart_tables_available": False,
            "excel_source": "local processed data",
            "excel_path": str(self.workbook_path),
        }


class MotherDuckJobRepository(JobRepository):
    """Queries dbt mart tables from MotherDuck."""

    def __init__(self, service: MotherDuckService | None = None) -> None:
        self.service = service or MotherDuckService()

    def _query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        return _records(self.service.query_df(sql, params))

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        clauses: list[str] = []
        params: list[Any] = []
        if filters.category_name:
            clauses.append("category_name = ?")
            params.append(filters.category_name)
        if filters.min_match_score is not None:
            clauses.append("match_score >= ?")
            params.append(filters.min_match_score)

        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        count_df = self.service.query_df(
            f"select count(*) as total from mart.mart_jobs_scored {where_sql}",
            params,
        )
        total = int(count_df.iloc[0]["total"]) if not count_df.empty else 0
        items = self._query(
            f"""
            select *
            from mart.mart_jobs_scored
            {where_sql}
            order by match_score desc, inserted_at desc
            limit ? offset ?
            """,
            [*params, filters.limit, filters.offset],
        )
        return PaginatedJobs(total=total, items=items)

    def get_top_matches(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_top_matches")

    def get_category_summary(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_category_summary")

    def get_skill_gap(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_skill_gap_analysis")

    def get_company_priority(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_company_priority_list")

    def get_status(self) -> dict[str, Any]:
        run_rows = self._query(
            """
            select
                run_id,
                run_started_at,
                run_completed_at,
                status,
                excel_output_path
            from raw.ingestion_runs
            order by run_started_at desc
            limit 1
            """
        )
        mart_count = self._query(
            """
            select count(*) as table_count
            from information_schema.tables
            where table_schema = 'mart'
              and table_name in (
                'mart_jobs_scored',
                'mart_top_matches',
                'mart_category_summary',
                'mart_skill_gap_analysis',
                'mart_company_priority_list'
              )
            """
        )
        table_count = int(mart_count[0]["table_count"]) if mart_count else 0
        latest_run = run_rows[0] if run_rows else {}
        return {
            "data_mode": "motherduck",
            "database": "MotherDuck",
            "motherduck_database": self.service.database,
            "last_pipeline_run": latest_run.get("run_completed_at") or latest_run.get("run_started_at"),
            "last_dbt_run": latest_run.get("run_completed_at"),
            "mart_tables_available": table_count == 5,
            "excel_source": "MotherDuck mart tables",
            "excel_path": latest_run.get("excel_output_path"),
            "latest_run_status": latest_run.get("status"),
        }


def build_job_repository() -> JobRepository:
    if data_mode() == "motherduck":
        return MotherDuckJobRepository()
    return LocalJobRepository()
