"""USAJOBS Search API connector."""

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


class USAJobsConnector(BaseJobConnector):
    """Fetches active federal job announcements from USAJOBS."""

    source_name = "usajobs"
    search_url = "https://data.usajobs.gov/api/search"

    def __init__(
        self,
        api_key: str | None = None,
        user_agent: str | None = None,
        global_filters: GlobalFilters | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("USAJOBS_API_KEY")
        self.user_agent = user_agent or os.getenv("USAJOBS_USER_AGENT")
        self.global_filters = global_filters
        self.max_queries_per_category = env_int("USAJOBS_MAX_QUERIES_PER_CATEGORY", 2)
        self.results_per_page = env_int("USAJOBS_RESULTS_PER_PAGE", 25)
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.session = session or requests.Session()
        self._missing_credentials_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.api_key or not self.user_agent:
            if not self._missing_credentials_warned:
                LOGGER.warning("USAJOBS credentials are missing; returning no jobs.")
                self._missing_credentials_warned = True
            return []

        jobs: list[dict[str, Any]] = []
        for title, location in limited_search_pairs(
            category_config,
            self.global_filters,
            self.max_queries_per_category,
        ):
            payload = safe_get_json(
                self.session,
                self.search_url,
                params=self._build_params(title, location),
                headers=self._headers(),
                timeout=self.timeout,
                source_name=self.source_name,
            )
            if not isinstance(payload, dict):
                continue
            search_result = payload.get("SearchResult")
            if not isinstance(search_result, dict):
                continue
            items = search_result.get("SearchResultItems", [])
            if not isinstance(items, list):
                continue
            jobs.extend(
                self._map_result(item, category_config)
                for item in items
                if isinstance(item, dict)
            )
        return jobs

    def _headers(self) -> dict[str, str]:
        return {
            "Host": "data.usajobs.gov",
            "User-Agent": str(self.user_agent),
            "Authorization-Key": str(self.api_key),
        }

    def _build_params(self, title: str, location: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "Keyword": title,
            "ResultsPerPage": self.results_per_page,
            "Page": 1,
            "SortField": "OpenDate",
        }
        if location and location.casefold() != "remote":
            params["LocationName"] = location
        return params

    def _map_result(
        self,
        item: dict[str, Any],
        category_config: JobCategoryConfig,
    ) -> dict[str, Any]:
        descriptor = item.get("MatchedObjectDescriptor")
        if not isinstance(descriptor, dict):
            descriptor = {}
        user_area = descriptor.get("UserArea") if isinstance(descriptor.get("UserArea"), dict) else {}
        details = user_area.get("Details") if isinstance(user_area.get("Details"), dict) else {}

        return {
            "source": self.source_name,
            "external_id": clean_text(descriptor.get("PositionID") or item.get("MatchedObjectId")),
            "category_name": category_config.category_name,
            "title": clean_text(descriptor.get("PositionTitle")),
            "company": clean_text(descriptor.get("OrganizationName")) or "USAJOBS",
            "industry": "Government",
            "location": clean_text(descriptor.get("PositionLocationDisplay")) or "Unknown",
            "employment_type": clean_text(descriptor.get("PositionSchedule", [{}])[0].get("Name"))
            if isinstance(descriptor.get("PositionSchedule"), list) and descriptor.get("PositionSchedule")
            else "full-time",
            "salary": self._salary_text(descriptor),
            "date_posted": clean_text(descriptor.get("PublicationStartDate")) or None,
            "jd_post_link": clean_text(descriptor.get("PositionURI")),
            "apply_link": self._apply_link(descriptor),
            "description": self._description(details),
            "raw_source_record": item,
        }

    def _apply_link(self, descriptor: dict[str, Any]) -> str | None:
        apply_uri = descriptor.get("ApplyURI")
        if isinstance(apply_uri, list) and apply_uri:
            return clean_text(apply_uri[0]) or None
        return clean_text(apply_uri) or None

    def _description(self, details: dict[str, Any]) -> str:
        fields = [
            "JobSummary",
            "MajorDuties",
            "Requirements",
            "Evaluations",
            "Education",
            "HowToApply",
        ]
        return clean_text(" ".join(clean_text(details.get(field)) for field in fields))

    def _salary_text(self, descriptor: dict[str, Any]) -> str:
        remuneration = descriptor.get("PositionRemuneration")
        if not isinstance(remuneration, list) or not remuneration:
            return ""
        first = remuneration[0]
        if not isinstance(first, dict):
            return ""
        minimum = first.get("MinimumRange")
        maximum = first.get("MaximumRange")
        description = clean_text(first.get("Description"))
        interval = clean_text(first.get("RateIntervalCode"))
        if description:
            return description
        if minimum and maximum:
            return f"{minimum} - {maximum} {interval}".strip()
        if minimum:
            return f"{minimum} {interval}".strip()
        if maximum:
            return f"{maximum} {interval}".strip()
        return ""
