"""Greenhouse public Job Board API connector."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Any, Callable, Iterable

import requests

from src.config.schemas import GlobalFilters, JobCategoryConfig
from src.connectors.base import BaseJobConnector
from src.connectors.http_utils import (
    env_float,
    env_int,
    matches_category,
    safe_get_json,
    split_env,
)
from src.utils.hashing import stable_hash
from src.utils.text_cleaning import clean_text

LOGGER = logging.getLogger(__name__)


class GreenhouseConnector(BaseJobConnector):
    """Fetches public jobs from configured Greenhouse job boards."""

    source_name = "greenhouse"
    base_url = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        company_tokens: list[str] | None = None,
        global_filters: GlobalFilters | None = None,
        session: requests.Session | None = None,
        state: dict[tuple[str, str], dict[str, Any]] | None = None,
        detail_concurrency: int | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.company_tokens = company_tokens or split_env("GREENHOUSE_COMPANY_TOKENS")
        self.global_filters = global_filters
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.session = session or requests.Session()
        default_detail_concurrency = 1 if session is not None else 8
        self.detail_concurrency = min(
            16,
            detail_concurrency
            or env_int(
                "GREENHOUSE_DETAIL_MAX_CONCURRENCY",
                default_detail_concurrency,
            ),
        )
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._state = dict(state or {})
        self._state_updates: dict[tuple[str, str], dict[str, Any]] = {}
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._missing_tokens_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        jobs = self.fetch_jobs_for_categories([category_config])
        return [
            {
                key: value
                for key, value in job.items()
                if key != "_careersignal_category"
            }
            for job in jobs
        ]

    def fetch_jobs_for_categories(
        self,
        categories: Iterable[JobCategoryConfig],
    ) -> list[dict[str, Any]]:
        """Fetch each board once and assign every recent job to its first match."""

        if not self.company_tokens:
            if not self._missing_tokens_warned:
                LOGGER.warning("No Greenhouse company tokens configured; returning no jobs.")
                self._missing_tokens_warned = True
            return []

        board_jobs: list[dict[str, Any]] = []
        board_total = len(self.company_tokens)
        for board_index, token in enumerate(self.company_tokens, start=1):
            board_jobs.extend(
                self._fetch_board_jobs(
                    token,
                    board_index=board_index,
                    board_total=board_total,
                )
            )

        matched_jobs: list[dict[str, Any]] = []
        matched_job_keys: set[tuple[str, str, str]] = set()
        for category_config in categories:
            for job in board_jobs:
                job_key = (
                    clean_text(job.get("company")),
                    clean_text(job.get("external_id")),
                    clean_text(job.get("jd_post_link")),
                )
                if job_key in matched_job_keys:
                    continue
                if matches_category(
                    title=str(job.get("title") or ""),
                    description=str(job.get("description") or ""),
                    category_config=category_config,
                ):
                    matched_job_keys.add(job_key)
                    matched_jobs.append(
                        {
                            **job,
                            "category_name": category_config.category_name,
                            "_careersignal_category": category_config,
                        }
                    )
        return matched_jobs

    @property
    def state_updates(self) -> list[dict[str, Any]]:
        return list(self._state_updates.values())

    def _fetch_board_jobs(
        self,
        token: str,
        *,
        board_index: int,
        board_total: int,
    ) -> list[dict[str, Any]]:
        if token in self._cache:
            return self._cache[token]

        started_at = time.monotonic()
        payload = safe_get_json(
            self.session,
            f"{self.base_url}/{token}/jobs",
            timeout=self.timeout,
            source_name=self.source_name,
        )
        if not isinstance(payload, dict):
            self._cache[token] = []
            self._log_board_completed(board_index, board_total, 0, started_at)
            return []

        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            self._cache[token] = []
            self._log_board_completed(board_index, board_total, 0, started_at)
            return []

        listed_jobs = [job for job in jobs if isinstance(job, dict)]
        mapped, detail_requests, cache_hits = self._resolve_board_details(
            token,
            listed_jobs,
        )
        self._cache[token] = mapped
        LOGGER.info(
            "Greenhouse board state resolved "
            "(board=%s/%s, listed=%s, detail_requests=%s, cache_hits=%s)",
            board_index,
            board_total,
            len(listed_jobs),
            detail_requests,
            cache_hits,
        )
        self._log_board_completed(board_index, board_total, len(mapped), started_at)
        return mapped

    def _resolve_board_details(
        self,
        token: str,
        listed_jobs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], int, int]:
        board_key = stable_hash(token, length=32)
        resolved: list[dict[str, Any] | None] = [None] * len(listed_jobs)
        detail_candidates: list[tuple[int, str, str, dict[str, Any] | None]] = []
        cache_hits = 0

        for index, listed_job in enumerate(listed_jobs):
            job_post_id = clean_text(listed_job.get("id"))
            if not job_post_id:
                continue
            upstream_updated_at = clean_text(listed_job.get("updated_at"))
            cached = self._state.get((board_key, job_post_id))
            cached_payload = cached.get("detail_payload") if isinstance(cached, dict) else None
            if (
                isinstance(cached_payload, dict)
                and clean_text(cached.get("upstream_updated_at")) == upstream_updated_at
            ):
                cached_detail = dict(cached_payload)
                cached_detail.setdefault(
                    "first_published",
                    clean_text(cached.get("first_published_at")),
                )
                resolved[index] = {**cached_detail, **listed_job}
                cache_hits += 1
                continue
            if not isinstance(cached_payload, dict) and self._older_than_window(
                upstream_updated_at
            ):
                # Greenhouse cannot publish a job after its last update. On a cold
                # cache, this safely avoids detail calls for inventory that cannot
                # fall inside the first-published window.
                continue
            detail_candidates.append(
                (index, job_post_id, upstream_updated_at, cached if isinstance(cached, dict) else None)
            )

        def fetch_candidate(
            candidate: tuple[int, str, str, dict[str, Any] | None],
        ) -> dict[str, Any] | None:
            return self._fetch_job_detail(token, candidate[1])

        if self.detail_concurrency > 1 and len(detail_candidates) > 1:
            with ThreadPoolExecutor(
                max_workers=min(self.detail_concurrency, len(detail_candidates)),
                thread_name_prefix="greenhouse-detail",
            ) as executor:
                fetched_details = list(executor.map(fetch_candidate, detail_candidates))
        else:
            fetched_details = [fetch_candidate(candidate) for candidate in detail_candidates]

        for candidate, detail in zip(detail_candidates, fetched_details):
            index, job_post_id, upstream_updated_at, cached = candidate
            if not isinstance(detail, dict):
                cached_payload = cached.get("detail_payload") if isinstance(cached, dict) else None
                if isinstance(cached_payload, dict):
                    cached_detail = dict(cached_payload)
                    cached_detail.setdefault(
                        "first_published",
                        clean_text(cached.get("first_published_at")),
                    )
                    resolved[index] = {**cached_detail, **listed_jobs[index]}
                continue
            first_published_at = clean_text(
                detail.get("first_published") or detail.get("first_published_at")
            )
            state_record = {
                "board_key": board_key,
                "job_post_id": job_post_id,
                "upstream_updated_at": upstream_updated_at,
                "first_published_at": first_published_at,
                "detail_payload": self._state_detail_payload(detail),
            }
            self._state[(board_key, job_post_id)] = state_record
            self._state_updates[(board_key, job_post_id)] = state_record
            resolved[index] = detail

        recent_jobs: list[dict[str, Any]] = []
        for detail in resolved:
            if not isinstance(detail, dict):
                continue
            first_published_at = clean_text(
                detail.get("first_published") or detail.get("first_published_at")
            )
            published_at = self._parse_timestamp(first_published_at)
            if published_at is None or not self._within_last_24_hours(published_at):
                continue
            recent_jobs.append(
                self._map_result(
                    detail,
                    token,
                    first_published_at=self._format_timestamp(published_at),
                )
            )
        return recent_jobs, len(detail_candidates), cache_hits

    def _fetch_job_detail(self, token: str, job_post_id: str) -> dict[str, Any] | None:
        payload = safe_get_json(
            self.session,
            f"{self.base_url}/{token}/jobs/{job_post_id}",
            timeout=self.timeout,
            source_name=self.source_name,
        )
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _state_detail_payload(detail: dict[str, Any]) -> dict[str, Any]:
        """Cache only fields required to rebuild a mapped job on later runs."""

        cacheable_fields = (
            "id",
            "internal_job_id",
            "title",
            "first_published",
            "first_published_at",
            "updated_at",
            "location",
            "departments",
            "offices",
            "content",
        )
        return {field: detail[field] for field in cacheable_fields if field in detail}

    def _within_last_24_hours(self, published_at: datetime) -> bool:
        now = self._now_utc()
        return now - timedelta(hours=24) <= published_at <= now

    def _older_than_window(self, value: Any) -> bool:
        updated_at = self._parse_timestamp(value)
        return (
            updated_at is not None
            and updated_at < self._now_utc() - timedelta(hours=24)
        )

    def _now_utc(self) -> datetime:
        now = self._now_provider()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        text = clean_text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _log_board_completed(
        board_index: int,
        board_total: int,
        jobs: int,
        started_at: float,
    ) -> None:
        elapsed_ms = round((time.monotonic() - started_at) * 1000)
        LOGGER.info(
            "Greenhouse board completed (board=%s/%s, jobs=%s, elapsed_ms=%s)",
            board_index,
            board_total,
            jobs,
            elapsed_ms,
        )

    def _map_result(
        self,
        result: dict[str, Any],
        token: str,
        *,
        first_published_at: str,
    ) -> dict[str, Any]:
        location = result.get("location") if isinstance(result.get("location"), dict) else {}
        departments = result.get("departments") if isinstance(result.get("departments"), list) else []
        department_names = [
            clean_text(department.get("name"))
            for department in departments
            if isinstance(department, dict) and clean_text(department.get("name"))
        ]
        description = clean_text(
            " ".join(
                [
                    str(result.get("content") or ""),
                    " ".join(department_names),
                ]
            )
        )

        return {
            "source": self.source_name,
            "external_id": clean_text(result.get("id") or result.get("internal_job_id")),
            "title": clean_text(result.get("title")),
            "company": token,
            "industry": "Unknown",
            "location": clean_text(location.get("name")) or "Unknown",
            "employment_type": "full-time",
            "salary": "",
            "date_posted": first_published_at,
            "posted_at": first_published_at,
            "jd_post_link": clean_text(result.get("absolute_url")),
            "apply_link": clean_text(result.get("absolute_url")) or None,
            "description": description,
            "raw_source_record": result,
        }
