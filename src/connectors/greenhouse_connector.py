"""Greenhouse public Job Board API connector."""

from __future__ import annotations

from datetime import datetime
import logging
import os
from typing import Any

import requests

from src.config.schemas import GlobalFilters, JobCategoryConfig
from src.connectors.base import BaseJobConnector
from src.connectors.http_utils import env_float, matches_category, safe_get_json, split_env
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
    ) -> None:
        self.company_tokens = company_tokens or split_env("GREENHOUSE_COMPANY_TOKENS")
        self.global_filters = global_filters
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.session = session or requests.Session()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._missing_tokens_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.company_tokens:
            if not self._missing_tokens_warned:
                LOGGER.warning("No Greenhouse company tokens configured; returning no jobs.")
                self._missing_tokens_warned = True
            return []

        matched_jobs: list[dict[str, Any]] = []
        for token in self.company_tokens:
            for job in self._fetch_board_jobs(token):
                if matches_category(
                    title=str(job.get("title") or ""),
                    description=str(job.get("description") or ""),
                    category_config=category_config,
                ):
                    matched_jobs.append({**job, "category_name": category_config.category_name})
        return matched_jobs

    def _fetch_board_jobs(self, token: str) -> list[dict[str, Any]]:
        if token in self._cache:
            return self._cache[token]

        payload = safe_get_json(
            self.session,
            f"{self.base_url}/{token}/jobs",
            params={"content": "true"},
            timeout=self.timeout,
            source_name=self.source_name,
        )
        if not isinstance(payload, dict):
            self._cache[token] = []
            return []

        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            self._cache[token] = []
            return []

        mapped = [
            self._map_result(result, token)
            for result in jobs
            if isinstance(result, dict)
        ]
        self._cache[token] = mapped
        return mapped

    def _map_result(self, result: dict[str, Any], token: str) -> dict[str, Any]:
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
            "date_posted": self._date_from_updated_at(result.get("updated_at")),
            "jd_post_link": clean_text(result.get("absolute_url")),
            "apply_link": clean_text(result.get("absolute_url")) or None,
            "description": description,
            "raw_source_record": result,
        }

    def _date_from_updated_at(self, value: Any) -> str | None:
        text = clean_text(value)
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return text
