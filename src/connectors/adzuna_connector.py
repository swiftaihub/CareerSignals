"""Adzuna job-search API connector."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from src.config.schemas import GlobalFilters, JobCategoryConfig
from src.connectors.base import BaseJobConnector
from src.connectors.http_utils import env_float, env_int, limited_search_pairs, safe_get_json
from src.utils.text_cleaning import clean_text

LOGGER = logging.getLogger(__name__)


class AdzunaConnector(BaseJobConnector):
    """Fetches jobs from the Adzuna search API."""

    source_name = "adzuna"
    base_url = "https://api.adzuna.com/v1/api/jobs"

    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
        global_filters: GlobalFilters | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.app_id = app_id or os.getenv("ADZUNA_APP_ID")
        self.app_key = app_key or os.getenv("ADZUNA_APP_KEY")
        self.global_filters = global_filters
        self.country = (
            os.getenv("ADZUNA_COUNTRY")
            or (global_filters.country if global_filters else "US")
        ).casefold()
        self.results_per_page = env_int("ADZUNA_RESULTS_PER_PAGE", 25)
        self.max_pages = env_int("ADZUNA_MAX_PAGES", 1)
        self.max_queries_per_category = env_int("ADZUNA_MAX_QUERIES_PER_CATEGORY", 4)
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.session = session or requests.Session()
        self._missing_credentials_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.app_id or not self.app_key:
            if not self._missing_credentials_warned:
                LOGGER.warning("Adzuna credentials are missing; returning no jobs.")
                self._missing_credentials_warned = True
            return []

        jobs: list[dict[str, Any]] = []
        for title, location in limited_search_pairs(
            category_config,
            self.global_filters,
            self.max_queries_per_category,
        ):
            for page in range(1, self.max_pages + 1):
                payload = safe_get_json(
                    self.session,
                    f"{self.base_url}/{self.country}/search/{page}",
                    params=self._build_params(title, location),
                    timeout=self.timeout,
                    source_name=self.source_name,
                )
                if not isinstance(payload, dict):
                    continue
                results = payload.get("results", [])
                if not isinstance(results, list):
                    continue
                jobs.extend(
                    self._map_result(result, category_config)
                    for result in results
                    if isinstance(result, dict)
                )
        return jobs

    def _build_params(self, title: str, location: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": self.results_per_page,
            "what": title,
            "content-type": "application/json",
            "sort_by": "date",
        }
        if location:
            params["where"] = location
        return params

    def _map_result(
        self,
        result: dict[str, Any],
        category_config: JobCategoryConfig,
    ) -> dict[str, Any]:
        company = result.get("company") if isinstance(result.get("company"), dict) else {}
        location = result.get("location") if isinstance(result.get("location"), dict) else {}
        category = result.get("category") if isinstance(result.get("category"), dict) else {}
        salary_text = self._salary_text(result)

        return {
            "source": self.source_name,
            "external_id": clean_text(result.get("id")),
            "category_name": category_config.category_name,
            "title": clean_text(result.get("title")),
            "company": clean_text(company.get("display_name")),
            "industry": clean_text(category.get("label")),
            "location": clean_text(location.get("display_name")),
            "employment_type": "full-time",
            "salary": salary_text,
            "date_posted": clean_text(result.get("created")) or None,
            "jd_post_link": clean_text(result.get("redirect_url")),
            "apply_link": clean_text(result.get("redirect_url")) or None,
            "description": clean_text(result.get("description")),
            "raw_source_record": result,
        }

    def _salary_text(self, result: dict[str, Any]) -> str:
        salary_min = result.get("salary_min")
        salary_max = result.get("salary_max")
        if salary_min and salary_max:
            return f"{salary_min} - {salary_max}"
        if salary_min:
            return str(salary_min)
        if salary_max:
            return str(salary_max)
        return ""
