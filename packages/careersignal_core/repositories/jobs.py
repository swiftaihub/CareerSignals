"""Job repository abstraction for local and MotherDuck modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

import pandas as pd

from packages.careersignal_core.settings import (
    data_mode,
    dbt_profiles_dir,
    dbt_project_dir,
    excel_path,
    output_dir,
    project_root,
)
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.loader import load_configs
from src.utils.hashing import stable_hash

PERSONAL_USER_ID = "personal_user"
TOP_MATCH_THRESHOLD = 80
APPLICATION_STATUSES = {
    "Not Applied",
    "Saved",
    "Applied",
    "Interview",
    "Rejected",
    "Offer",
    "Archived",
}

DISPLAY_COLUMN_MAP: dict[str, str] = {
    "Job ID": "job_id",
    "Category": "category_name",
    "Match Tier": "match_tier",
    "Match Score": "match_score",
    "Job Title": "job_title",
    "Normalized Title": "normalized_title",
    "Company": "company",
    "Industry": "industry",
    "Location": "location",
    "Work Arrangement": "work_arrangement",
    "Seniority": "seniority",
    "Employment Type": "employment_type",
    "Salary Range": "salary_range_text",
    "Salary Min": "salary_min",
    "Salary Max": "salary_max",
    "Salary Midpoint": "salary_midpoint",
    "Visa Signal": "visa_signal",
    "Required Skills": "required_skills",
    "Preferred Skills": "preferred_skills",
    "All Extracted Skills": "all_extracted_skills",
    "JD Post Link": "jd_post_link",
    "Apply Link": "apply_link",
    "Date Posted": "date_posted",
    "Date Collected": "date_collected",
    "Source": "source",
    "Application Status": "application_status",
    "Reasoning Summary": "reasoning_summary",
    "Jobs Found": "jobs_found",
    "Excellent Matches": "excellent_matches",
    "Strong Matches": "strong_matches",
    "Good Matches": "good_matches",
    "Average Match Score": "average_match_score",
    "Average Salary Midpoint": "average_salary_midpoint",
    "Remote Count": "remote_count",
    "Hybrid Count": "hybrid_count",
    "On-site Count": "onsite_count",
    "Unknown Work Arrangement Count": "unknown_work_arrangement_count",
    "Positive Visa Signal Count": "positive_visa_signal_count",
    "Negative Visa Signal Count": "negative_visa_signal_count",
    "Unknown Visa Signal Count": "unknown_visa_signal_count",
    "Skill": "skill",
    "Skill Group": "skill_group",
    "Appears In Job Count": "appears_in_job_count",
    "Appears In Job %": "appears_in_job_pct",
    "In Candidate Profile": "in_candidate_profile",
    "Gap Priority": "gap_priority",
    "Example Matching Job Titles": "example_matching_job_titles",
    "Matching Roles Count": "matching_roles_count",
    "Highest Match Score": "highest_match_score",
    "Best Matching Role": "best_matching_role",
    "Visa Signal Summary": "visa_signal_summary",
    "Priority": "priority",
}

SKILL_FIELDS = {"required_skills", "preferred_skills", "all_extracted_skills"}
NUMERIC_FIELDS = {
    "match_score",
    "salary_min",
    "salary_max",
    "salary_midpoint",
    "jobs_found",
    "excellent_matches",
    "strong_matches",
    "good_matches",
    "average_match_score",
    "average_salary_midpoint",
    "remote_count",
    "hybrid_count",
    "onsite_count",
    "unknown_work_arrangement_count",
    "positive_visa_signal_count",
    "negative_visa_signal_count",
    "unknown_visa_signal_count",
    "appears_in_job_count",
    "appears_in_job_pct",
    "matching_roles_count",
    "highest_match_score",
}
SEARCH_FIELDS = (
    "job_title",
    "company",
    "industry",
    "location",
    "required_skills",
    "preferred_skills",
    "all_extracted_skills",
    "reasoning_summary",
)
SORT_COLUMNS = {
    "match_score",
    "salary_midpoint",
    "date_posted",
    "date_collected",
    "company",
    "job_title",
    "category_name",
}
MART_JOB_COLUMNS = [
    "job_id",
    "category_name",
    "match_tier",
    "match_score",
    "job_title",
    "normalized_title",
    "company",
    "industry",
    "location",
    "work_arrangement",
    "seniority",
    "employment_type",
    "salary_range_text",
    "salary_min",
    "salary_max",
    "salary_midpoint",
    "visa_signal",
    "required_skills",
    "preferred_skills",
    "all_extracted_skills",
    "jd_post_link",
    "apply_link",
    "date_posted",
    "date_collected",
    "source",
    "reasoning_summary",
    "run_id",
    "inserted_at",
]


@dataclass(frozen=True)
class JobFilters:
    limit: int = 100
    offset: int = 0
    page: int | None = None
    page_size: int | None = None
    category_name: str | None = None
    min_match_score: float | None = None
    max_match_score: float | None = None
    company: str | None = None
    industry: str | None = None
    location: str | None = None
    work_arrangement: str | None = None
    visa_signal: str | None = None
    application_status: str | None = None
    search: str | None = None
    sort_by: str = "match_score"
    sort_order: str = "desc"

    @property
    def resolved_limit(self) -> int:
        return self.page_size or self.limit

    @property
    def resolved_offset(self) -> int:
        if self.page is not None:
            return max(self.page - 1, 0) * self.resolved_limit
        return self.offset

    @property
    def resolved_page(self) -> int:
        if self.page is not None:
            return self.page
        return (self.resolved_offset // max(self.resolved_limit, 1)) + 1

    @property
    def resolved_page_size(self) -> int:
        return self.resolved_limit

    @property
    def resolved_sort_by(self) -> str:
        return self.sort_by if self.sort_by in SORT_COLUMNS else "match_score"

    @property
    def resolved_sort_order(self) -> str:
        return "asc" if self.sort_order.casefold() == "asc" else "desc"


@dataclass(frozen=True)
class PaginatedJobs:
    total: int
    items: list[dict[str, Any]]
    page: int
    page_size: int
    limit: int
    offset: int


class JobRepository(ABC):
    @abstractmethod
    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        raise NotImplementedError

    @abstractmethod
    def get_job(self, job_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str = PERSONAL_USER_ID,
    ) -> dict[str, Any]:
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

    def get_dashboard_summary(self) -> dict[str, Any]:
        jobs_page = self.get_jobs(JobFilters(limit=5000, sort_by="match_score", sort_order="desc"))
        jobs = jobs_page.items
        total_jobs = jobs_page.total
        score_values = [_number(job.get("match_score")) for job in jobs]
        salary_values = [_number(job.get("salary_midpoint")) for job in jobs]
        top_matches = [job for job in jobs if (_number(job.get("match_score")) or 0) >= TOP_MATCH_THRESHOLD]

        return {
            "data_status": self.get_status(),
            "metrics": {
                "total_jobs": total_jobs,
                "top_matches": len(top_matches),
                "average_match_score": _average(score_values),
                "average_salary_midpoint": _average(salary_values),
                "remote_or_hybrid_roles": sum(
                    1
                    for job in jobs
                    if str(job.get("work_arrangement") or "").casefold() in {"remote", "hybrid"}
                ),
                "positive_or_unknown_visa_roles": sum(
                    1
                    for job in jobs
                    if str(job.get("visa_signal") or "").casefold() in {"positive", "unknown", ""}
                ),
            },
            "category_summary": self.get_category_summary(),
            "top_matches_preview": top_matches[:10],
            "visa_signal_distribution": _distribution(jobs, "visa_signal"),
            "work_arrangement_distribution": _distribution(jobs, "work_arrangement"),
            "match_tier_distribution": _distribution(jobs, "match_tier"),
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, str):
        cleaned = value.replace("$", "").replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _average(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 1)


def _distribution(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(field) or "Unknown") for row in rows)
    return [{"label": label, "count": count} for label, count in counts.most_common()]


def _records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    if dataframe.empty:
        return []
    clean = dataframe.where(pd.notna(dataframe), None)
    return [_normalize_record(row) for row in clean.to_dict(orient="records")]


def _snake_case(value: str) -> str:
    value = re.sub(r"[^0-9a-zA-Z]+", "_", value).strip("_")
    return value.casefold()


def _parse_skill_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def _normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for key, value in row.items():
        api_key = DISPLAY_COLUMN_MAP.get(str(key), str(key))
        api_key = _snake_case(api_key) if " " in api_key else api_key
        if api_key in SKILL_FIELDS:
            record[api_key] = _parse_skill_value(value)
        elif api_key in NUMERIC_FIELDS:
            record[api_key] = _number(value)
        else:
            record[api_key] = value

    if not record.get("job_id") and (record.get("job_title") or record.get("company")):
        record["job_id"] = stable_hash(
            "local",
            record.get("job_title"),
            record.get("company"),
            record.get("location"),
            record.get("jd_post_link"),
            record.get("apply_link"),
            length=20,
        )
    if not record.get("application_status"):
        record["application_status"] = "Not Applied"
    return record


def _text_match(value: Any, needle: str) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        haystack = " ".join(str(item) for item in value)
    else:
        haystack = str(value)
    return needle in haystack.casefold()


def _contains_filter(record_value: Any, filter_value: str | None) -> bool:
    if not filter_value:
        return True
    return str(filter_value).casefold() in str(record_value or "").casefold()


def _apply_local_filters(rows: list[dict[str, Any]], filters: JobFilters) -> list[dict[str, Any]]:
    filtered = rows
    if filters.category_name:
        filtered = [row for row in filtered if row.get("category_name") == filters.category_name]
    if filters.min_match_score is not None:
        filtered = [
            row for row in filtered if (_number(row.get("match_score")) or 0) >= filters.min_match_score
        ]
    if filters.max_match_score is not None:
        filtered = [
            row for row in filtered if (_number(row.get("match_score")) or 0) <= filters.max_match_score
        ]
    for field in ("company", "industry", "location", "work_arrangement", "visa_signal", "application_status"):
        value = getattr(filters, field)
        if value:
            filtered = [row for row in filtered if _contains_filter(row.get(field), value)]
    if filters.search:
        needle = filters.search.casefold().strip()
        filtered = [
            row
            for row in filtered
            if any(_text_match(row.get(field), needle) for field in SEARCH_FIELDS)
        ]

    reverse = filters.resolved_sort_order == "desc"
    sort_by = filters.resolved_sort_by

    def sort_key(row: dict[str, Any]) -> tuple[int, Any]:
        value = row.get(sort_by)
        if sort_by in {"match_score", "salary_midpoint"}:
            return (value is None, _number(value) or 0)
        return (value is None, str(value or "").casefold())

    return sorted(filtered, key=sort_key, reverse=reverse)


def _status_sidecar_path() -> Path:
    return output_dir() / "job_application_status.json"


def _operation_state_path() -> Path:
    return output_dir() / "api_operation_status.json"


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_local_statuses() -> dict[str, dict[str, Any]]:
    raw = _read_json_file(_status_sidecar_path())
    statuses = raw.get(PERSONAL_USER_ID, raw)
    return statuses if isinstance(statuses, dict) else {}


def _safe_project_path(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = (project_root() / resolved).resolve()
    try:
        return resolved.relative_to(project_root()).as_posix()
    except ValueError:
        return resolved.name


def _configured_sources() -> list[str]:
    raw_sources = os.getenv("JOB_SOURCES") or os.getenv("JOB_SOURCE") or "mock"
    sources = [source.strip() for source in raw_sources.split(",") if source.strip()]
    return sources or ["mock"]


def _configured_categories() -> list[str]:
    try:
        configs = load_configs(project_root())
    except Exception:
        return []
    return [category.category_name for category in configs.jobs.job_categories]


def _base_status(
    *,
    mode: str,
    database: str,
    motherduck_database: str | None = None,
    mart_tables_available: bool | None = None,
    excel_source: str | None = None,
    excel_path_value: str | Path | None = None,
    latest_run_status: str | None = None,
    last_pipeline_run_at: Any | None = None,
    last_dbt_run_at: Any | None = None,
    last_dbt_test_at: Any | None = None,
) -> dict[str, Any]:
    operation_state = _read_json_file(_operation_state_path())
    path_value = operation_state.get("excel_path") or excel_path_value
    resolved_excel = Path(path_value) if path_value else None
    if resolved_excel and not resolved_excel.is_absolute():
        resolved_excel = (project_root() / resolved_excel).resolve()

    return {
        "data_mode": mode,
        "database": database,
        "motherduck_database": motherduck_database,
        "mart_tables_available": mart_tables_available,
        "last_pipeline_run_at": operation_state.get("last_pipeline_run_at") or last_pipeline_run_at,
        "last_pipeline_run": operation_state.get("last_pipeline_run_at") or last_pipeline_run_at,
        "last_dbt_run_at": operation_state.get("last_dbt_run_at") or last_dbt_run_at,
        "last_dbt_run": operation_state.get("last_dbt_run_at") or last_dbt_run_at,
        "last_dbt_test_at": operation_state.get("last_dbt_test_at") or last_dbt_test_at,
        "excel_path": _safe_project_path(path_value),
        "excel_exists": bool(resolved_excel and resolved_excel.exists()),
        "excel_source": excel_source,
        "local_mode_available": True,
        "motherduck_mode_available": bool(os.getenv("MOTHERDUCK_TOKEN")),
        "dbt_project_dir": _safe_project_path(dbt_project_dir()),
        "dbt_profiles_dir": _safe_project_path(dbt_profiles_dir()),
        "configured_sources": _configured_sources(),
        "job_sources": _configured_categories(),
        "latest_run_status": latest_run_status,
    }


def write_operation_state(**updates: Any) -> None:
    state = _read_json_file(_operation_state_path())
    state.update(updates)
    _write_json_file(_operation_state_path(), state)


class LocalJobRepository(JobRepository):
    """Reads latest local Excel workbook as a fallback data source."""

    def __init__(self, workbook_path: str | Path | None = None) -> None:
        self.workbook_path = self._resolve_workbook_path(Path(workbook_path or excel_path()))

    def _resolve_workbook_path(self, configured_path: Path) -> Path:
        if configured_path.exists():
            return configured_path

        output_path = configured_path.parent
        timestamped_pattern = f"{configured_path.stem}_*.xlsx"
        candidates = sorted(
            output_path.glob(timestamped_pattern),
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

    def _jobs(self) -> list[dict[str, Any]]:
        rows = _records(self._sheet("All Jobs"))
        statuses = _read_local_statuses()
        for row in rows:
            status = statuses.get(str(row.get("job_id")))
            if isinstance(status, dict):
                row["application_status"] = status.get("application_status") or row.get("application_status")
                row["notes"] = status.get("notes")
                row["application_updated_at"] = status.get("updated_at")
        return rows

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        filtered = _apply_local_filters(self._jobs(), filters)
        total = len(filtered)
        offset = filters.resolved_offset
        limit = filters.resolved_limit
        return PaginatedJobs(
            total=total,
            items=filtered[offset : offset + limit],
            page=filters.resolved_page,
            page_size=filters.resolved_page_size,
            limit=limit,
            offset=offset,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        for job in self._jobs():
            if str(job.get("job_id")) == str(job_id):
                return job
        return None

    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str = PERSONAL_USER_ID,
    ) -> dict[str, Any]:
        if application_status not in APPLICATION_STATUSES:
            raise ValueError(f"Unsupported application status: {application_status}")
        if self.get_job(job_id) is None:
            raise KeyError(job_id)

        state = _read_json_file(_status_sidecar_path())
        user_state = state.get(user_id)
        if not isinstance(user_state, dict):
            user_state = {}
        payload = {
            "job_id": job_id,
            "application_status": application_status,
            "notes": notes,
            "updated_at": _now_iso(),
        }
        user_state[job_id] = payload
        state[user_id] = user_state
        _write_json_file(_status_sidecar_path(), state)
        return payload

    def get_top_matches(self) -> list[dict[str, Any]]:
        return _apply_local_filters(
            self._jobs(),
            JobFilters(
                limit=5000,
                min_match_score=TOP_MATCH_THRESHOLD,
                sort_by="match_score",
                sort_order="desc",
            ),
        )

    def get_category_summary(self) -> list[dict[str, Any]]:
        return _records(self._sheet("By Category Summary"))

    def get_skill_gap(self) -> list[dict[str, Any]]:
        return _records(self._sheet("Skill Gap Analysis"))

    def get_company_priority(self) -> list[dict[str, Any]]:
        return _records(self._sheet("Company Priority List"))

    def get_status(self) -> dict[str, Any]:
        return _base_status(
            mode="local",
            database="Local",
            mart_tables_available=False,
            excel_source="local processed data",
            excel_path_value=self.workbook_path,
        )


class MotherDuckJobRepository(JobRepository):
    """Queries dbt mart tables from MotherDuck."""

    def __init__(self, service: MotherDuckService | None = None) -> None:
        self.service = service or MotherDuckService()

    def _query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        return _records(self.service.query_df(sql, params))

    def _jobs_base_sql(self) -> str:
        selected_columns = ",\n                ".join(f"jobs.{column}" for column in MART_JOB_COLUMNS)
        return f"""
            with latest_status as (
                select
                    user_id,
                    job_id,
                    application_status,
                    notes,
                    updated_at
                from (
                    select
                        *,
                        row_number() over (
                            partition by user_id, job_id
                            order by updated_at desc
                        ) as rn
                    from app.job_application_status
                    where user_id = ?
                )
                where rn = 1
            ),
            jobs_with_status as (
                select
                    {selected_columns},
                    coalesce(latest_status.application_status, jobs.application_status, 'Not Applied') as application_status,
                    latest_status.notes,
                    latest_status.updated_at as application_updated_at
                from mart.mart_jobs_scored as jobs
                left join latest_status
                    on jobs.job_id = latest_status.job_id
            )
        """

    def _where_sql(self, filters: JobFilters) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = [PERSONAL_USER_ID]
        exact_filters = {
            "category_name": filters.category_name,
            "work_arrangement": filters.work_arrangement,
            "visa_signal": filters.visa_signal,
            "application_status": filters.application_status,
        }
        contains_filters = {
            "company": filters.company,
            "industry": filters.industry,
            "location": filters.location,
        }

        for column, value in exact_filters.items():
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        for column, value in contains_filters.items():
            if value:
                clauses.append(f"lower(coalesce({column}, '')) like ?")
                params.append(f"%{value.casefold()}%")
        if filters.min_match_score is not None:
            clauses.append("match_score >= ?")
            params.append(filters.min_match_score)
        if filters.max_match_score is not None:
            clauses.append("match_score <= ?")
            params.append(filters.max_match_score)
        if filters.search:
            search_sql = " || ' ' || ".join(f"coalesce(cast({field} as varchar), '')" for field in SEARCH_FIELDS)
            clauses.append(f"lower({search_sql}) like ?")
            params.append(f"%{filters.search.casefold()}%")

        where_sql = f"where {' and '.join(clauses)}" if clauses else ""
        return where_sql, params

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        where_sql, params = self._where_sql(filters)
        base_sql = self._jobs_base_sql()
        count_df = self.service.query_df(
            f"{base_sql} select count(*) as total from jobs_with_status {where_sql}",
            params,
        )
        total = int(count_df.iloc[0]["total"]) if not count_df.empty else 0
        order_column = filters.resolved_sort_by
        order_direction = filters.resolved_sort_order
        nulls = "nulls last"
        items = self._query(
            f"""
            {base_sql}
            select *
            from jobs_with_status
            {where_sql}
            order by {order_column} {order_direction} {nulls}, match_score desc nulls last
            limit ? offset ?
            """,
            [*params, filters.resolved_limit, filters.resolved_offset],
        )
        return PaginatedJobs(
            total=total,
            items=items,
            page=filters.resolved_page,
            page_size=filters.resolved_page_size,
            limit=filters.resolved_limit,
            offset=filters.resolved_offset,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        filters = JobFilters(limit=1)
        base_sql = self._jobs_base_sql()
        rows = self._query(
            f"""
            {base_sql}
            select *
            from jobs_with_status
            where job_id = ?
            limit 1
            """,
            [PERSONAL_USER_ID, job_id],
        )
        return rows[0] if rows else None

    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str = PERSONAL_USER_ID,
    ) -> dict[str, Any]:
        if application_status not in APPLICATION_STATUSES:
            raise ValueError(f"Unsupported application status: {application_status}")
        if self.get_job(job_id) is None:
            raise KeyError(job_id)

        init_motherduck_schema(self.service)
        updated_at = _now_iso()
        self.service.execute(
            """
            insert or replace into app.job_application_status (
                user_id,
                job_id,
                application_status,
                notes,
                updated_at
            )
            values (?, ?, ?, ?, ?)
            """,
            [user_id, job_id, application_status, notes, updated_at],
        )
        return {
            "job_id": job_id,
            "application_status": application_status,
            "notes": notes,
            "updated_at": updated_at,
        }

    def get_top_matches(self) -> list[dict[str, Any]]:
        return self.get_jobs(
            JobFilters(
                limit=5000,
                min_match_score=TOP_MATCH_THRESHOLD,
                sort_by="match_score",
                sort_order="desc",
            )
        ).items

    def get_category_summary(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_category_summary")

    def get_skill_gap(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_skill_gap_analysis")

    def get_company_priority(self) -> list[dict[str, Any]]:
        return self._query("select * from mart.mart_company_priority_list")

    def get_status(self) -> dict[str, Any]:
        try:
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
        except Exception:
            run_rows = []

        try:
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
        except Exception:
            table_count = 0

        latest_run = run_rows[0] if run_rows else {}
        return _base_status(
            mode="motherduck",
            database="MotherDuck",
            motherduck_database=self.service.database,
            mart_tables_available=table_count == 5,
            excel_source="MotherDuck mart tables",
            excel_path_value=latest_run.get("excel_output_path"),
            latest_run_status=latest_run.get("status"),
            last_pipeline_run_at=latest_run.get("run_completed_at") or latest_run.get("run_started_at"),
            last_dbt_run_at=latest_run.get("run_completed_at"),
        )


def build_job_repository() -> JobRepository:
    if data_mode() == "motherduck":
        return MotherDuckJobRepository()
    return LocalJobRepository()
