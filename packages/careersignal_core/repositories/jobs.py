"""Job repository abstraction for local and MotherDuck modes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
import re
import threading
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from packages.careersignal_core.settings import (
    data_mode,
    dbt_profiles_dir,
    dbt_project_dir,
    excel_path,
    output_dir,
    project_root,
)
from packages.careersignal_core.repositories.dashboard_analytics import (
    DASHBOARD_TIMEZONE,
    DashboardAnalyticsRepository,
)
from packages.careersignal_core.storage.motherduck import MotherDuckService
from packages.careersignal_core.storage.postgres import PostgresStore
from packages.careersignal_core.storage.schema import init_motherduck_schema
from src.config.loader import load_configs
from src.processing.location_normalization import (
    build_location_facets,
    normalize_location,
)
from src.processing.visa_signal import NO_SPONSORSHIP, SPONSORSHIP_AVAILABLE, UNKNOWN_STATUS
from src.utils.hashing import stable_hash

LEGACY_LOCAL_USER_UUID = "00000000-0000-0000-0000-000000000001"
TOP_MATCH_THRESHOLD = 80
PIPELINE_DAILY_REFRESH_LIMIT = 2
PIPELINE_QUOTA_RESET_HOUR = 6
EASTERN_TZ = ZoneInfo("America/New_York")
APPLICATION_STATUSES = {
    "Not Applied",
    "Saved",
    "Applied",
    "Interview",
    "Rejected",
    "Offer",
    "Archived",
    "not_started",
    "saved",
    "applied",
    "interview",
    "rejected",
    "offer",
    "archived",
}

APPLICATION_STATUS_STORAGE = {
    "not applied": "not_started",
    "not_started": "not_started",
    "saved": "saved",
    "applied": "applied",
    "interview": "interview",
    "rejected": "rejected",
    "offer": "offer",
    "archived": "archived",
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
    "Location Normalized": "location_normalized",
    "Location Group": "location_group",
    "Work Arrangement": "work_arrangement",
    "Seniority": "seniority",
    "Employment Type": "employment_type",
    "Salary Range": "salary_range_text",
    "Salary Min": "salary_min",
    "Salary Max": "salary_max",
    "Salary Midpoint": "salary_midpoint",
    "Visa Signal": "visa_signal",
    "Visa Status": "visa_status",
    "Visa Evidence": "visa_evidence",
    "Visa Confidence": "visa_confidence",
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
FILTER_OPTION_FIELDS = {
    "categories": "category_name",
    "companies": "company",
    "industries": "industry",
    "locations": "location",
}
FILTER_OPTION_LIMIT = 500
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
    "location_normalized",
    "location_group",
    "work_arrangement",
    "seniority",
    "employment_type",
    "salary_range_text",
    "salary_min",
    "salary_max",
    "salary_midpoint",
    "visa_signal",
    "visa_status",
    "visa_evidence",
    "visa_confidence",
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
    location_group: str | None = None
    work_arrangement: str | None = None
    visa_signal: str | None = None
    application_status: str | None = None
    search: str | None = None
    posted_start_date: date | str | None = None
    posted_end_date: date | str | None = None
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
        user_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_filter_options(self) -> dict[str, list[str]]:
        raise NotImplementedError

    @abstractmethod
    def get_facets(self) -> dict[str, Any]:
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

    def get_dashboard_summary(self, *, days: int = 30) -> dict[str, Any]:
        if not 7 <= days <= 365:
            raise ValueError("days must be between 7 and 365")
        jobs_page = self.get_jobs(JobFilters(limit=5000, sort_by="match_score", sort_order="desc"))
        jobs = jobs_page.items
        total_jobs = jobs_page.total
        score_values = [_number(job.get("match_score")) for job in jobs]
        salary_values = [_number(job.get("salary_midpoint")) for job in jobs]
        top_matches = [job for job in jobs if (_number(job.get("match_score")) or 0) >= TOP_MATCH_THRESHOLD]

        applied_statuses = {"applied", "interview", "rejected", "offer"}
        interview_statuses = {"interview", "offer"}
        applied_jobs = sum(
            1
            for job in jobs
            if str(job.get("application_status") or "").strip().casefold()
            in applied_statuses
        )
        interview_jobs = sum(
            1
            for job in jobs
            if str(job.get("application_status") or "").strip().casefold()
            in interview_statuses
        )
        end_date = datetime.now(DASHBOARD_TIMEZONE).date()
        start_date = end_date - timedelta(days=days - 1)

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
            "funnel": {
                "total_global_jobs": total_jobs,
                "total_user_jobs": total_jobs,
                "total_applied_jobs": applied_jobs,
                "total_interviews": interview_jobs,
            },
            # Local and legacy MotherDuck modes have no trustworthy historical
            # snapshots. An empty series is preferable to invented daily data.
            "job_count_timeseries": [],
            "analytics_window": {
                "start_date": start_date,
                "end_date": end_date,
                "days": days,
            },
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _now_et() -> datetime:
    return datetime.now(EASTERN_TZ).replace(microsecond=0)


def _iso_et(value: datetime | None = None) -> str:
    return (value or _now_et()).astimezone(EASTERN_TZ).replace(microsecond=0).isoformat()


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(EASTERN_TZ)


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


def _json_ready_value(value: Any) -> Any:
    if not isinstance(value, (dict, list, tuple, set)):
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


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
            record[api_key] = _json_ready_value(value)

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
    return _apply_derived_fields(record)


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


def _location_matches(row: dict[str, Any], query: str | None) -> bool:
    if not query:
        return True
    needle = query.casefold().strip()
    if not needle:
        return True
    haystack = " ".join(
        str(row.get(field) or "")
        for field in ("location", "location_normalized", "location_group")
    ).casefold()
    return needle in haystack


def _apply_derived_fields(record: dict[str, Any]) -> dict[str, Any]:
    location_result = normalize_location(record.get("location"))
    if not record.get("location_normalized"):
        record["location_normalized"] = location_result.normalized
    if not record.get("location_group"):
        record["location_group"] = location_result.group
    if not record.get("visa_status"):
        signal = str(record.get("visa_signal") or "Unknown")
        if signal == "Positive":
            record["visa_status"] = SPONSORSHIP_AVAILABLE
        elif signal == "Negative":
            record["visa_status"] = NO_SPONSORSHIP
        else:
            record["visa_status"] = UNKNOWN_STATUS
    if not record.get("visa_confidence"):
        record["visa_confidence"] = "Low"
    return record


def _coerce_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    if isinstance(parsed, pd.Timestamp):
        return parsed.date()
    return None


def _date_in_range(record_value: Any, start_date: date | str | None, end_date: date | str | None) -> bool:
    posted_date = _coerce_date(record_value)
    if posted_date is None:
        return False
    resolved_start = _coerce_date(start_date)
    resolved_end = _coerce_date(end_date)
    if resolved_start and posted_date < resolved_start:
        return False
    if resolved_end and posted_date > resolved_end:
        return False
    return True


def _option_values(rows: list[dict[str, Any]], field: str, limit: int = FILTER_OPTION_LIMIT) -> list[str]:
    values = {
        str(row.get(field) or "").strip()
        for row in rows
        if str(row.get(field) or "").strip()
    }
    return sorted(values, key=str.casefold)[:limit]


def _apply_local_filters(rows: list[dict[str, Any]], filters: JobFilters) -> list[dict[str, Any]]:
    filtered = [_apply_derived_fields(dict(row)) for row in rows]
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
    for field in ("company", "industry", "work_arrangement", "visa_signal", "application_status"):
        value = getattr(filters, field)
        if value:
            filtered = [row for row in filtered if _contains_filter(row.get(field), value)]
    if filters.location_group:
        filtered = [row for row in filtered if row.get("location_group") == filters.location_group]
    if filters.location:
        filtered = [row for row in filtered if _location_matches(row, filters.location)]
    if filters.search:
        needle = filters.search.casefold().strip()
        filtered = [
            row
            for row in filtered
            if any(_text_match(row.get(field), needle) for field in SEARCH_FIELDS)
        ]
    if filters.posted_start_date or filters.posted_end_date:
        filtered = [
            row
            for row in filtered
            if _date_in_range(row.get("date_posted"), filters.posted_start_date, filters.posted_end_date)
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


_OPERATION_STATE_LOCK = threading.RLock()


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


def read_operation_state() -> dict[str, Any]:
    with _OPERATION_STATE_LOCK:
        return _read_json_file(_operation_state_path())


class PipelineQuotaExceededError(RuntimeError):
    def __init__(self, quota: dict[str, Any]) -> None:
        super().__init__("Daily pipeline refresh limit reached.")
        self.quota = quota


def _quota_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or _now_et()).astimezone(EASTERN_TZ)
    today_reset = datetime.combine(
        current.date(),
        time(hour=PIPELINE_QUOTA_RESET_HOUR),
        tzinfo=EASTERN_TZ,
    )
    window_start = today_reset if current >= today_reset else today_reset - timedelta(days=1)
    return window_start, window_start + timedelta(days=1)


def _history_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    history = state.get("pipeline_run_history")
    return history if isinstance(history, list) else []


def _pipeline_runs_from_state(state: dict[str, Any]) -> dict[str, Any]:
    runs = state.get("pipeline_runs")
    return runs if isinstance(runs, dict) else {}


def _pipeline_quota_from_state(
    state: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    window_start, window_end = _quota_window(now)
    used = 0
    for run in _history_from_state(state):
        started_at = _parse_iso_datetime(run.get("started_at"))
        if started_at and window_start <= started_at < window_end:
            used += 1

    remaining = max(PIPELINE_DAILY_REFRESH_LIMIT - used, 0)
    return {
        "limit": PIPELINE_DAILY_REFRESH_LIMIT,
        "used": min(used, PIPELINE_DAILY_REFRESH_LIMIT),
        "remaining": remaining,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "resets_at": window_end.isoformat(),
    }


def get_pipeline_quota(now: datetime | None = None) -> dict[str, Any]:
    with _OPERATION_STATE_LOCK:
        return _pipeline_quota_from_state(_read_json_file(_operation_state_path()), now)


def _new_pipeline_message(message: str, level: str = "info") -> dict[str, str]:
    return {
        "timestamp": _iso_et(),
        "level": level,
        "message": message,
    }


def reserve_pipeline_run(run_id: str) -> dict[str, Any]:
    with _OPERATION_STATE_LOCK:
        state = _read_json_file(_operation_state_path())
        quota = _pipeline_quota_from_state(state)
        if quota["remaining"] <= 0:
            raise PipelineQuotaExceededError(quota)

        started_at = _iso_et()
        run_record = {
            "run_id": run_id,
            "status": "running",
            "started_at": started_at,
            "completed_at": None,
            "messages": [_new_pipeline_message("Pipeline started")],
            "summary": None,
        }

        runs = _pipeline_runs_from_state(state)
        runs[run_id] = run_record
        state["pipeline_runs"] = runs

        history = _history_from_state(state)
        history.append({"run_id": run_id, "started_at": started_at, "status": "running"})
        window_start, _ = _quota_window()
        history_floor = window_start - timedelta(days=7)
        state["pipeline_run_history"] = [
            item
            for item in history
            if (_parse_iso_datetime(item.get("started_at")) or _now_et()) >= history_floor
        ]
        _write_json_file(_operation_state_path(), state)
        return run_record


def _update_history_status(state: dict[str, Any], run_id: str, status: str) -> None:
    for item in _history_from_state(state):
        if item.get("run_id") == run_id:
            item["status"] = status


def get_pipeline_run_state(run_id: str) -> dict[str, Any] | None:
    with _OPERATION_STATE_LOCK:
        run = _pipeline_runs_from_state(_read_json_file(_operation_state_path())).get(run_id)
        return run if isinstance(run, dict) else None


def append_pipeline_run_message(run_id: str, message: str, level: str = "info") -> None:
    if not message.strip():
        return
    with _OPERATION_STATE_LOCK:
        state = _read_json_file(_operation_state_path())
        runs = _pipeline_runs_from_state(state)
        run = runs.get(run_id)
        if not isinstance(run, dict):
            return
        messages = run.get("messages")
        if not isinstance(messages, list):
            messages = []
        if messages and messages[-1].get("message") == message:
            return
        messages.append(_new_pipeline_message(message.strip(), level))
        run["messages"] = messages[-200:]
        runs[run_id] = run
        state["pipeline_runs"] = runs
        _write_json_file(_operation_state_path(), state)


def complete_pipeline_run_state(run_id: str, summary: dict[str, Any]) -> dict[str, Any] | None:
    with _OPERATION_STATE_LOCK:
        state = _read_json_file(_operation_state_path())
        runs = _pipeline_runs_from_state(state)
        run = runs.get(run_id)
        if not isinstance(run, dict):
            return None
        run["status"] = "completed"
        run["completed_at"] = _iso_et()
        run["summary"] = summary
        messages = run.get("messages") if isinstance(run.get("messages"), list) else []
        messages.append(_new_pipeline_message("Pipeline completed successfully"))
        run["messages"] = messages[-200:]
        runs[run_id] = run
        state["pipeline_runs"] = runs
        _update_history_status(state, run_id, "completed")
        _write_json_file(_operation_state_path(), state)
        return run


def fail_pipeline_run_state(run_id: str, error_message: str) -> dict[str, Any] | None:
    with _OPERATION_STATE_LOCK:
        state = _read_json_file(_operation_state_path())
        runs = _pipeline_runs_from_state(state)
        run = runs.get(run_id)
        if not isinstance(run, dict):
            return None
        run["status"] = "failed"
        run["completed_at"] = _iso_et()
        run["summary"] = {"error": error_message}
        messages = run.get("messages") if isinstance(run.get("messages"), list) else []
        messages.append(_new_pipeline_message(error_message, "error"))
        run["messages"] = messages[-200:]
        runs[run_id] = run
        state["pipeline_runs"] = runs
        _update_history_status(state, run_id, "failed")
        _write_json_file(_operation_state_path(), state)
        return run


def _read_local_statuses(user_uuid: str = LEGACY_LOCAL_USER_UUID) -> dict[str, dict[str, Any]]:
    raw = _read_json_file(_status_sidecar_path())
    statuses = raw.get(user_uuid, raw)
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
    operation_state = read_operation_state()
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
        "pipeline_quota": _pipeline_quota_from_state(operation_state),
    }


def write_operation_state(**updates: Any) -> None:
    with _OPERATION_STATE_LOCK:
        state = _read_json_file(_operation_state_path())
        state.update(updates)
        _write_json_file(_operation_state_path(), state)


class LocalJobRepository(JobRepository):
    """Reads latest local Excel workbook as a fallback data source."""

    def __init__(
        self,
        workbook_path: str | Path | None = None,
        user_uuid: str = LEGACY_LOCAL_USER_UUID,
    ) -> None:
        self.workbook_path = self._resolve_workbook_path(Path(workbook_path or excel_path()))
        self.user_uuid = user_uuid

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
        statuses = _read_local_statuses(self.user_uuid)
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
        user_id: str | None = None,
    ) -> dict[str, Any]:
        if application_status not in APPLICATION_STATUSES:
            raise ValueError(f"Unsupported application status: {application_status}")
        if self.get_job(job_id) is None:
            raise KeyError(job_id)

        state = _read_json_file(_status_sidecar_path())
        owner = user_id or self.user_uuid
        user_state = state.get(owner)
        if not isinstance(user_state, dict):
            user_state = {}
        payload = {
            "job_id": job_id,
            "application_status": application_status,
            "notes": notes,
            "updated_at": _now_iso(),
        }
        user_state[job_id] = payload
        state[owner] = user_state
        _write_json_file(_status_sidecar_path(), state)
        return payload

    def get_filter_options(self) -> dict[str, list[str]]:
        rows = self._jobs()
        return {
            option_name: _option_values(rows, field)
            for option_name, field in FILTER_OPTION_FIELDS.items()
        }

    def get_facets(self) -> dict[str, Any]:
        rows = self._jobs()
        return build_location_facets(row.get("location") for row in rows)

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

    def __init__(
        self,
        service: MotherDuckService | None = None,
        user_uuid: str = LEGACY_LOCAL_USER_UUID,
    ) -> None:
        self.service = service or MotherDuckService()
        self.user_uuid = user_uuid
        self._available_columns: set[str] | None = None

    def _query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        return _records(self.service.query_df(sql, params))

    def _mart_columns(self) -> set[str]:
        if self._available_columns is not None:
            return self._available_columns
        try:
            rows = self._query(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'mart'
                  and table_name = 'mart_jobs_scored'
                """
            )
        except Exception:
            rows = []
        self._available_columns = {str(row.get("column_name")) for row in rows if row.get("column_name")}
        return self._available_columns

    def _select_job_columns_sql(self) -> str:
        available = self._mart_columns()
        expressions: list[str] = []
        for column in MART_JOB_COLUMNS:
            if not available or column in available:
                expressions.append(f"jobs.{column}")
            else:
                expressions.append(f"cast(null as varchar) as {column}")
        return ",\n                ".join(expressions)

    def _jobs_base_sql(self) -> str:
        selected_columns = self._select_job_columns_sql()
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
        params: list[Any] = [self.user_uuid]
        available_columns = self._mart_columns()
        exact_filters = {
            "category_name": filters.category_name,
            "work_arrangement": filters.work_arrangement,
            "visa_signal": filters.visa_signal,
            "application_status": filters.application_status,
        }
        contains_filters = {
            "company": filters.company,
            "industry": filters.industry,
        }

        for column, value in exact_filters.items():
            if value:
                clauses.append(f"{column} = ?")
                params.append(value)
        for column, value in contains_filters.items():
            if value:
                clauses.append(f"lower(coalesce({column}, '')) like ?")
                params.append(f"%{value.casefold()}%")
        if filters.location_group:
            group_locations = self._location_values_for_group(filters.location_group)
            if "location_group" in available_columns:
                if group_locations:
                    placeholders = ", ".join("?" for _ in group_locations)
                    clauses.append(
                        f"(location_group = ? or (location_group is null and coalesce(location, '') in ({placeholders})))"
                    )
                    params.append(filters.location_group)
                    params.extend(group_locations)
                else:
                    clauses.append("location_group = ?")
                    params.append(filters.location_group)
            elif group_locations:
                placeholders = ", ".join("?" for _ in group_locations)
                clauses.append(f"coalesce(location, '') in ({placeholders})")
                params.extend(group_locations)
            else:
                clauses.append("1 = 0")
        if filters.location:
            if "location_normalized" in available_columns:
                location_sql = "coalesce(location, '') || ' ' || coalesce(location_normalized, '')"
            else:
                location_sql = "coalesce(location, '')"
            clauses.append(f"lower({location_sql}) like ?")
            params.append(f"%{filters.location.casefold()}%")
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
        if filters.posted_start_date or filters.posted_end_date:
            posted_date_expr = "coalesce(try_cast(date_posted as date), cast(try_cast(date_posted as timestamp) as date))"
            if filters.posted_start_date:
                clauses.append(f"{posted_date_expr} >= ?")
                params.append(str(_coerce_date(filters.posted_start_date)))
            if filters.posted_end_date:
                clauses.append(f"{posted_date_expr} <= ?")
                params.append(str(_coerce_date(filters.posted_end_date)))

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
            [self.user_uuid, job_id],
        )
        return rows[0] if rows else None

    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str | None = None,
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
            [user_id or self.user_uuid, job_id, application_status, notes, updated_at],
        )
        return {
            "job_id": job_id,
            "application_status": application_status,
            "notes": notes,
            "updated_at": updated_at,
        }

    def _location_counts(self) -> list[dict[str, Any]]:
        return self._query(
            """
            select
                location,
                count(*) as count
            from mart.mart_jobs_scored
            where location is not null
              and trim(cast(location as varchar)) <> ''
            group by location
            """
        )

    def _location_values_for_group(self, location_group: str) -> list[str]:
        values: list[str] = []
        for row in self._location_counts():
            location_value = str(row.get("location") or "")
            if normalize_location(location_value).group == location_group:
                values.append(location_value)
        return values

    def get_filter_options(self) -> dict[str, list[str]]:
        options: dict[str, list[str]] = {}
        for option_name, field in FILTER_OPTION_FIELDS.items():
            rows = self._query(
                f"""
                select distinct trim(cast({field} as varchar)) as value
                from mart.mart_jobs_scored
                where {field} is not null
                  and trim(cast({field} as varchar)) <> ''
                order by value
                limit {FILTER_OPTION_LIMIT}
                """
            )
            options[option_name] = [str(row["value"]) for row in rows if row.get("value")]
        return options

    def get_facets(self) -> dict[str, Any]:
        locations: list[str] = []
        for row in self._location_counts():
            count = int(_number(row.get("count")) or 0)
            locations.extend([row.get("location")] * max(count, 0))
        return build_location_facets(locations)

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


class PostgresJobRepository(JobRepository):
    """Tenant-scoped serving repository backed by PostgreSQL current partitions."""

    def __init__(
        self,
        user_uuid: str,
        store: PostgresStore | None = None,
        *,
        is_demo: bool = False,
    ) -> None:
        if not user_uuid:
            raise ValueError("A verified user UUID is required")
        self.user_uuid = str(user_uuid)
        self.store = store or PostgresStore()
        self.is_demo = is_demo
        self.dashboard_analytics = DashboardAnalyticsRepository(self.store)

    @staticmethod
    def _status_display_sql() -> str:
        return """
            case coalesce(status.application_status, 'not_started')
              when 'not_started' then 'Not Applied'
              else initcap(status.application_status)
            end
        """

    def _base_sql(self) -> str:
        status_display = self._status_display_sql()
        return f"""
            select
                jobs.job_id,
                matches.category_name,
                case
                  when matches.match_score >= 90 then 'Excellent Match'
                  when matches.match_score >= 80 then 'Strong Match'
                  when matches.match_score >= 70 then 'Good Match'
                  else 'Low Priority'
                end as match_tier,
                matches.match_score,
                jobs.title as job_title,
                jobs.title as normalized_title,
                jobs.company_name as company,
                jobs.industry,
                jobs.location,
                jobs.location as location_normalized,
                jobs.location_group,
                jobs.work_arrangement,
                jobs.seniority,
                null::text as employment_type,
                case
                  when jobs.salary_min is null and jobs.salary_max is null then null
                  else concat_ws(' - ', jobs.salary_min::text, jobs.salary_max::text)
                end as salary_range_text,
                jobs.salary_min,
                jobs.salary_max,
                case
                  when jobs.salary_min is not null and jobs.salary_max is not null
                    then (jobs.salary_min + jobs.salary_max) / 2.0
                  else coalesce(jobs.salary_min, jobs.salary_max)
                end as salary_midpoint,
                jobs.visa_signal,
                case
                  when lower(coalesce(jobs.visa_signal, '')) = 'positive' then 'Sponsorship Available'
                  when lower(coalesce(jobs.visa_signal, '')) = 'negative' then 'No Sponsorship'
                  else 'Unknown'
                end as visa_status,
                null::text as visa_evidence,
                'Low'::text as visa_confidence,
                matches.matched_skills as required_skills,
                '[]'::jsonb as preferred_skills,
                matches.matched_skills as all_extracted_skills,
                jobs.apply_url as jd_post_link,
                jobs.apply_url as apply_link,
                case
                  when jobs.posted_at >= timestamptz '1970-01-01'
                   and jobs.posted_at < timestamptz '2100-01-01'
                    then jobs.posted_at
                  else null
                end as date_posted,
                case
                  when jobs.last_seen_at >= timestamptz '1970-01-01'
                   and jobs.last_seen_at < timestamptz '2100-01-01'
                    then jobs.last_seen_at
                  else null
                end as date_collected,
                jobs.source_name as source,
                {status_display} as application_status,
                status.notes,
                status.updated_at as application_updated_at,
                matches.ranking_reasons as reasoning_summary,
                matches.run_uuid,
                matches.created_at as inserted_at,
                matches.title_score,
                matches.required_skill_score,
                matches.preferred_skill_score,
                matches.industry_score,
                matches.salary_score,
                matches.work_arrangement_score,
                matches.visa_score,
                matches.missing_skills,
                matches.is_top_match
            from public.user_job_matches matches
            join public.job_postings jobs on jobs.job_id = matches.job_id
            left join public.user_job_statuses status
              on status.user_uuid = matches.user_uuid and status.job_id = matches.job_id
            where matches.user_uuid = %s and matches.is_current = true
        """

    def _clauses(self, filters: JobFilters) -> tuple[list[str], list[Any]]:
        clauses: list[str] = []
        params: list[Any] = [self.user_uuid]
        exact = {
            "category_name": filters.category_name,
            "work_arrangement": filters.work_arrangement,
            "visa_signal": filters.visa_signal,
            "location_group": filters.location_group,
        }
        for column, value in exact.items():
            if value:
                clauses.append(f"lower(coalesce({column}, '')) = lower(%s)")
                params.append(value)
        contains = {
            "company": filters.company,
            "industry": filters.industry,
            "location": filters.location,
        }
        for column, value in contains.items():
            if value:
                clauses.append(f"coalesce({column}, '') ilike %s")
                params.append(f"%{value}%")
        if filters.application_status:
            clauses.append("lower(application_status) = lower(%s)")
            display = "Not Applied" if filters.application_status == "not_started" else filters.application_status
            params.append(display)
        if filters.min_match_score is not None:
            clauses.append("match_score >= %s")
            params.append(filters.min_match_score)
        if filters.max_match_score is not None:
            clauses.append("match_score <= %s")
            params.append(filters.max_match_score)
        if filters.search:
            clauses.append(
                "concat_ws(' ', job_title, company, industry, location, required_skills::text, reasoning_summary::text) ilike %s"
            )
            params.append(f"%{filters.search}%")
        if filters.posted_start_date:
            clauses.append("date_posted::date >= %s")
            params.append(_coerce_date(filters.posted_start_date))
        if filters.posted_end_date:
            clauses.append("date_posted::date <= %s")
            params.append(_coerce_date(filters.posted_end_date))
        return clauses, params

    def get_jobs(self, filters: JobFilters) -> PaginatedJobs:
        clauses, params = self._clauses(filters)
        outer_where = " where " + " and ".join(clauses) if clauses else ""
        base = self._base_sql()
        count = self.store.fetch_one(
            f"select count(*) as total from ({base}) scoped{outer_where}", params
        )
        sort_column = filters.resolved_sort_by
        items = self.store.fetch_all(
            f"""
            select * from ({base}) scoped
            {outer_where}
            order by {sort_column} {filters.resolved_sort_order} nulls last, match_score desc
            limit %s offset %s
            """,
            [*params, filters.resolved_limit, filters.resolved_offset],
        )
        return PaginatedJobs(
            total=int((count or {}).get("total", 0)),
            items=[_apply_derived_fields(_normalize_record(row)) for row in items],
            page=filters.resolved_page,
            page_size=filters.resolved_page_size,
            limit=filters.resolved_limit,
            offset=filters.resolved_offset,
        )

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        row = self.store.fetch_one(
            f"select * from ({self._base_sql()}) scoped where job_id = %s limit 1",
            [self.user_uuid, job_id],
        )
        return _apply_derived_fields(_normalize_record(row)) if row else None

    def update_job_status(
        self,
        job_id: str,
        application_status: str,
        notes: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        stored_status = APPLICATION_STATUS_STORAGE.get(application_status.strip().casefold())
        if stored_status is None:
            raise ValueError(f"Unsupported application status: {application_status}")
        with self.store.transaction() as connection:
            owned_match = connection.execute(
                """
                select 1
                from public.user_job_matches
                where user_uuid = %s::uuid
                  and job_id = %s
                  and is_current = true
                limit 1
                """,
                [self.user_uuid, job_id],
            ).fetchone()
            if owned_match is None:
                raise KeyError(job_id)
            row = connection.execute(
                """
                insert into public.user_job_statuses (
                  user_uuid, job_id, application_status, notes, updated_at
                ) values (%s::uuid, %s, %s, %s, now())
                on conflict (user_uuid, job_id) do update set
                  application_status = excluded.application_status,
                  notes = excluded.notes,
                  updated_at = now()
                returning job_id,
                  case application_status when 'not_started' then 'Not Applied'
                       else initcap(application_status) end as application_status,
                  notes, updated_at
                """,
                [self.user_uuid, job_id, stored_status, notes],
            ).fetchone()
        assert row is not None
        return dict(row)

    def get_dashboard_summary(self, *, days: int = 30) -> dict[str, Any]:
        if not 7 <= days <= 365:
            raise ValueError("days must be between 7 and 365")
        aggregate = self.store.fetch_one(
            """
            select
                count(distinct matches.job_id)::integer as total_jobs,
                count(distinct matches.job_id) filter (
                    where matches.match_score >= %s
                )::integer as top_matches,
                round(avg(matches.match_score), 1) as average_match_score,
                round(avg(
                    case
                        when jobs.salary_min is not null
                          and jobs.salary_min::text not in ('NaN', 'Infinity', '-Infinity')
                          and jobs.salary_max is not null
                          and jobs.salary_max::text not in ('NaN', 'Infinity', '-Infinity')
                            then (jobs.salary_min + jobs.salary_max) / 2.0
                        else coalesce(
                            case
                                when jobs.salary_min::text not in ('NaN', 'Infinity', '-Infinity')
                                    then jobs.salary_min
                            end,
                            case
                                when jobs.salary_max::text not in ('NaN', 'Infinity', '-Infinity')
                                    then jobs.salary_max
                            end
                        )
                    end
                ), 1) as average_salary_midpoint,
                count(distinct matches.job_id) filter (
                    where lower(coalesce(jobs.work_arrangement, '')) in ('remote', 'hybrid')
                )::integer as remote_or_hybrid_roles,
                count(distinct matches.job_id) filter (
                    where lower(coalesce(jobs.visa_signal, '')) in ('positive', 'unknown', '')
                )::integer as positive_or_unknown_visa_roles
            from public.user_job_matches as matches
            join public.job_postings as jobs on jobs.job_id = matches.job_id
            where matches.user_uuid = %s::uuid
              and matches.is_current = true
            """,
            [TOP_MATCH_THRESHOLD, self.user_uuid],
        ) or {}
        distribution_rows = self.store.fetch_all(
            """
            with scoped as (
                select
                    coalesce(nullif(btrim(jobs.visa_signal), ''), 'Unknown') as visa_signal,
                    coalesce(nullif(btrim(jobs.work_arrangement), ''), 'Unknown') as work_arrangement,
                    case
                        when matches.match_score >= 90 then 'Excellent Match'
                        when matches.match_score >= 80 then 'Strong Match'
                        when matches.match_score >= 70 then 'Good Match'
                        else 'Low Priority'
                    end as match_tier
                from public.user_job_matches as matches
                join public.job_postings as jobs on jobs.job_id = matches.job_id
                where matches.user_uuid = %s::uuid
                  and matches.is_current = true
            ), dimensions as (
                select 'visa_signal'::text as dimension, visa_signal as label from scoped
                union all
                select 'work_arrangement', work_arrangement from scoped
                union all
                select 'match_tier', match_tier from scoped
            )
            select dimension, label, count(*)::integer as count
            from dimensions
            group by dimension, label
            order by dimension, count desc, label
            """,
            [self.user_uuid],
        )
        distributions: dict[str, list[dict[str, Any]]] = {
            "visa_signal": [],
            "work_arrangement": [],
            "match_tier": [],
        }
        for row in distribution_rows:
            dimension = str(row["dimension"])
            distributions[dimension].append(
                {"label": str(row["label"]), "count": int(row["count"])}
            )
        preview_rows = self.store.fetch_all(
            f"""
            select *
            from ({self._base_sql()}) as scoped
            where match_score >= %s
            order by match_score desc nulls last
            limit 10
            """,
            [self.user_uuid, TOP_MATCH_THRESHOLD],
        )
        analytics = self.dashboard_analytics.get_analytics(
            user_uuid=self.user_uuid,
            days=days,
            is_demo=self.is_demo,
        )
        return {
            "data_status": self.get_status(),
            "metrics": {
                "total_jobs": int(aggregate.get("total_jobs") or 0),
                "top_matches": int(aggregate.get("top_matches") or 0),
                "average_match_score": _number(aggregate.get("average_match_score")),
                "average_salary_midpoint": _number(
                    aggregate.get("average_salary_midpoint")
                ),
                "remote_or_hybrid_roles": int(
                    aggregate.get("remote_or_hybrid_roles") or 0
                ),
                "positive_or_unknown_visa_roles": int(
                    aggregate.get("positive_or_unknown_visa_roles") or 0
                ),
            },
            "category_summary": self.get_category_summary(),
            "top_matches_preview": [
                _apply_derived_fields(_normalize_record(row)) for row in preview_rows
            ],
            "visa_signal_distribution": distributions["visa_signal"],
            "work_arrangement_distribution": distributions["work_arrangement"],
            "match_tier_distribution": distributions["match_tier"],
            **analytics.as_dict(),
        }

    def get_filter_options(self) -> dict[str, list[str]]:
        rows = self.get_jobs(JobFilters(limit=5000)).items
        return {
            option_name: _option_values(rows, field)
            for option_name, field in FILTER_OPTION_FIELDS.items()
        }

    def get_facets(self) -> dict[str, Any]:
        rows = self.get_jobs(JobFilters(limit=5000)).items
        return build_location_facets(row.get("location") for row in rows)

    def get_top_matches(self) -> list[dict[str, Any]]:
        return self.get_jobs(
            JobFilters(limit=5000, min_match_score=TOP_MATCH_THRESHOLD, sort_by="match_score")
        ).items

    def _summary(self, table: str, key: str) -> list[dict[str, Any]]:
        rows = self.store.fetch_all(
            f"""
            select {key}, metrics
            from public.{table}
            where user_uuid = %s and is_current = true
            order by {key}
            """,
            [self.user_uuid],
        )
        return [{key: row[key], **(row.get("metrics") or {})} for row in rows]

    def get_category_summary(self) -> list[dict[str, Any]]:
        return self._summary("user_category_summary", "category_name")

    def get_skill_gap(self) -> list[dict[str, Any]]:
        rows = self._summary("user_skill_gap", "canonical_skill")
        return [{"skill": row.pop("canonical_skill"), **row} for row in rows]

    def get_company_priority(self) -> list[dict[str, Any]]:
        rows = self._summary("user_company_priority", "company_name")
        return [{"company": row.pop("company_name"), **row} for row in rows]

    def get_status(self) -> dict[str, Any]:
        run = self.store.fetch_one(
            """
            select status::text as status, completed_at, published_at, jobs_matched
            from public.user_pipeline_runs
            where user_uuid = %s and is_current_result = true
            limit 1
            """,
            [self.user_uuid],
        ) or {}
        return {
            "data_mode": "postgres",
            "database": "PostgreSQL",
            "mart_tables_available": bool(run),
            "latest_run_status": run.get("status"),
            "last_pipeline_run_at": run.get("completed_at"),
            "data_as_of": run.get("published_at"),
            "jobs_matched": run.get("jobs_matched", 0),
        }


def build_job_repository(
    user_uuid: str | None = None,
    *,
    is_demo: bool = False,
) -> JobRepository:
    owner = user_uuid or LEGACY_LOCAL_USER_UUID
    if data_mode() == "postgres":
        return PostgresJobRepository(owner, is_demo=is_demo)
    if data_mode() == "motherduck":
        return MotherDuckJobRepository(user_uuid=owner)
    return LocalJobRepository(user_uuid=owner)
