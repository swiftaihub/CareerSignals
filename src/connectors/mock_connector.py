"""Mock/demo connector backed by local sample JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config.schemas import JobCategoryConfig
from src.connectors.base import BaseJobConnector
from src.utils.text_cleaning import normalized_lower


class MockJobConnector(BaseJobConnector):
    """Reads sample job postings from ``data/sample/sample_jobs.json``."""

    source_name = "mock"

    def __init__(self, sample_file: str | Path = "data/sample/sample_jobs.json") -> None:
        self.sample_file = Path(sample_file)

    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        if not self.sample_file.exists():
            raise FileNotFoundError(f"Sample jobs file not found: {self.sample_file}")

        with self.sample_file.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        if not isinstance(payload, list):
            raise ValueError(f"Expected sample job JSON list in {self.sample_file}")

        category_name = category_config.category_name.casefold()
        search_terms = [term.casefold() for term in category_config.search_titles]
        matched_jobs: list[dict[str, Any]] = []

        for raw_job in payload:
            if not isinstance(raw_job, dict):
                continue
            raw_category = str(raw_job.get("category_name", "")).casefold()
            if raw_category == category_name:
                matched_jobs.append({**raw_job, "source": raw_job.get("source") or self.source_name})
                continue
            if raw_category:
                continue

            title_and_text = normalized_lower(
                f"{raw_job.get('title', '')} {raw_job.get('job_title', '')} "
                f"{raw_job.get('description', '')} {raw_job.get('job_description', '')}"
            )
            if any(term and term in title_and_text for term in search_terms):
                matched_jobs.append({**raw_job, "source": raw_job.get("source") or self.source_name})

        return matched_jobs
