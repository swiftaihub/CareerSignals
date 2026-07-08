"""Lever public postings API connector."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

import requests

from src.config.schemas import GlobalFilters, JobCategoryConfig
from src.connectors.base import BaseJobConnector
from src.connectors.http_utils import env_float, matches_category, safe_get_json, split_env
from src.utils.text_cleaning import clean_text

LOGGER = logging.getLogger(__name__)


class LeverConnector(BaseJobConnector):
    """Fetches public jobs from configured Lever sites."""

    source_name = "lever"
    base_url = "https://api.lever.co/v0/postings"

    def __init__(
        self,
        company_sites: list[str] | None = None,
        global_filters: GlobalFilters | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.company_sites = company_sites or split_env("LEVER_COMPANY_SITES")
        self.global_filters = global_filters
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.session = session or requests.Session()
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._missing_sites_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.company_sites:
            if not self._missing_sites_warned:
                LOGGER.warning("No Lever company sites configured; returning no jobs.")
                self._missing_sites_warned = True
            return []

        matched_jobs: list[dict[str, Any]] = []
        for site in self.company_sites:
            for job in self._fetch_site_jobs(site):
                if matches_category(
                    title=str(job.get("title") or ""),
                    description=str(job.get("description") or ""),
                    category_config=category_config,
                ):
                    matched_jobs.append({**job, "category_name": category_config.category_name})
        return matched_jobs

    def _fetch_site_jobs(self, site: str) -> list[dict[str, Any]]:
        if site in self._cache:
            return self._cache[site]

        payload = safe_get_json(
            self.session,
            f"{self.base_url}/{site}",
            params={"mode": "json"},
            timeout=self.timeout,
            source_name=self.source_name,
        )
        if not isinstance(payload, list):
            self._cache[site] = []
            return []

        mapped = [
            self._map_result(result, site)
            for result in payload
            if isinstance(result, dict)
        ]
        self._cache[site] = mapped
        return mapped

    def _map_result(self, result: dict[str, Any], site: str) -> dict[str, Any]:
        categories = result.get("categories") if isinstance(result.get("categories"), dict) else {}
        content = result.get("content") if isinstance(result.get("content"), dict) else {}
        description = self._description_from_content(content)

        return {
            "source": self.source_name,
            "external_id": clean_text(result.get("id")),
            "title": clean_text(result.get("text")),
            "company": site,
            "industry": clean_text(categories.get("team") or categories.get("department")),
            "location": clean_text(categories.get("location")) or "Unknown",
            "employment_type": clean_text(categories.get("commitment")) or "full-time",
            "salary": self._salary_text(result),
            "date_posted": self._date_from_epoch_ms(result.get("createdAt")),
            "jd_post_link": clean_text(result.get("hostedUrl")),
            "apply_link": clean_text(result.get("applyUrl")) or None,
            "description": description,
            "raw_source_record": result,
        }

    def _description_from_content(self, content: dict[str, Any]) -> str:
        parts = [clean_text(content.get("description"))]
        lists = content.get("lists")
        if isinstance(lists, list):
            for item in lists:
                if not isinstance(item, dict):
                    continue
                parts.append(clean_text(item.get("text")))
                parts.append(clean_text(item.get("content")))
        return clean_text(" ".join(parts))

    def _salary_text(self, result: dict[str, Any]) -> str:
        salary_range = result.get("salaryRange")
        if not isinstance(salary_range, dict):
            return ""
        minimum = salary_range.get("min")
        maximum = salary_range.get("max")
        currency = clean_text(salary_range.get("currency")) or "USD"
        interval = clean_text(salary_range.get("interval"))
        if minimum and maximum:
            return f"{currency} {minimum} - {maximum} {interval}".strip()
        if minimum:
            return f"{currency} {minimum} {interval}".strip()
        if maximum:
            return f"{currency} {maximum} {interval}".strip()
        return ""

    def _date_from_epoch_ms(self, value: Any) -> str | None:
        try:
            milliseconds = int(value)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).date().isoformat()
