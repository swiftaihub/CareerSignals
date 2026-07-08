"""SerpApi Google Jobs connector."""

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


class SerpApiConnector(BaseJobConnector):
    """Fetches Google Jobs results through SerpApi."""

    source_name = "serpapi_google_jobs"
    search_url = "https://serpapi.com/search.json"

    def __init__(
        self,
        api_key: str | None = None,
        global_filters: GlobalFilters | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY")
        self.global_filters = global_filters
        self.max_queries_per_category = env_int("SERPAPI_MAX_QUERIES_PER_CATEGORY", 1)
        self.timeout = env_float("CONNECTOR_TIMEOUT_SECONDS", 15.0)
        self.google_domain = os.getenv("SERPAPI_GOOGLE_DOMAIN", "google.com")
        self.gl = os.getenv("SERPAPI_GL", "us")
        self.hl = os.getenv("SERPAPI_HL", "en")
        self.session = session or requests.Session()
        self._missing_credentials_warned = False

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.api_key:
            if not self._missing_credentials_warned:
                LOGGER.warning("SerpApi API key is missing; returning no jobs.")
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
                timeout=self.timeout,
                source_name=self.source_name,
            )
            if not isinstance(payload, dict):
                continue
            results = payload.get("jobs_results", [])
            if not isinstance(results, list):
                continue
            jobs.extend(
                self._map_result(result, category_config)
                for result in results
                if isinstance(result, dict)
            )
        return jobs

    def _build_params(self, title: str, location: str) -> dict[str, Any]:
        query_parts = [title, "full time"]
        if location.casefold() == "remote":
            query_parts.append("remote")

        params: dict[str, Any] = {
            "engine": "google_jobs",
            "q": " ".join(query_parts),
            "api_key": self.api_key,
            "google_domain": self.google_domain,
            "gl": self.gl,
            "hl": self.hl,
        }
        if location and location.casefold() != "remote":
            params["location"] = location
        return params

    def _map_result(
        self,
        result: dict[str, Any],
        category_config: JobCategoryConfig,
    ) -> dict[str, Any]:
        detected = result.get("detected_extensions")
        if not isinstance(detected, dict):
            detected = {}

        apply_options = result.get("apply_options")
        apply_link = None
        if isinstance(apply_options, list) and apply_options:
            first_option = apply_options[0]
            if isinstance(first_option, dict):
                apply_link = clean_text(first_option.get("link")) or None

        description = self._description_with_highlights(result)
        salary_text = self._salary_text(result)

        return {
            "source": self.source_name,
            "external_id": clean_text(result.get("job_id")),
            "category_name": category_config.category_name,
            "title": clean_text(result.get("title")),
            "company": clean_text(result.get("company_name")),
            "industry": clean_text(result.get("via")),
            "location": clean_text(result.get("location")),
            "employment_type": clean_text(detected.get("schedule_type")) or "full-time",
            "salary": salary_text,
            "date_posted": clean_text(detected.get("posted_at")) or None,
            "jd_post_link": clean_text(result.get("share_link")) or apply_link or "",
            "apply_link": apply_link,
            "description": description,
            "raw_source_record": result,
        }

    def _description_with_highlights(self, result: dict[str, Any]) -> str:
        parts = [clean_text(result.get("description"))]
        highlights = result.get("job_highlights")
        if isinstance(highlights, list):
            for highlight in highlights:
                if not isinstance(highlight, dict):
                    continue
                title = clean_text(highlight.get("title"))
                items = highlight.get("items")
                if isinstance(items, list):
                    parts.append(f"{title}: {' '.join(clean_text(item) for item in items)}")
        return clean_text(" ".join(parts))

    def _salary_text(self, result: dict[str, Any]) -> str:
        extensions = result.get("extensions")
        if not isinstance(extensions, list):
            return ""
        salary_like = [
            clean_text(extension)
            for extension in extensions
            if isinstance(extension, str) and any(token in extension for token in ("$", "USD", "salary"))
        ]
        return " ".join(salary_like)
