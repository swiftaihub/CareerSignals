"""Connector interfaces for job sources."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.config.schemas import JobCategoryConfig


class BaseJobConnector(ABC):
    """Base class for all job posting connectors."""

    source_name: str

    @abstractmethod
    def fetch_jobs(self, category_config: JobCategoryConfig) -> list[dict[str, Any]]:
        """Fetch raw job postings for a configured job category."""
