"""Shared HTTP and connector helpers."""

from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from src.config.schemas import GlobalFilters, JobCategoryConfig
from src.utils.text_cleaning import clean_text

LOGGER = logging.getLogger(__name__)


def _safe_url_for_log(url: str) -> str:
    """Return only a URL origin, excluding all request-specific components."""

    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not hostname:
            return "<redacted-url>"
        host = f"[{hostname}]" if ":" in hostname else hostname
        netloc = f"{host}:{parsed.port}" if parsed.port is not None else host
        return urlunsplit((parsed.scheme, netloc, "", "", ""))
    except (TypeError, ValueError):
        return "<redacted-url>"


def env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return max(minimum, int(raw_value))
    except ValueError:
        LOGGER.warning("Invalid integer for %s=%r; using %s.", name, raw_value, default)
        return default


def env_float(name: str, default: float, minimum: float = 0.1) -> float:
    raw_value = os.getenv(name)
    if not raw_value:
        return default
    try:
        return max(minimum, float(raw_value))
    except ValueError:
        LOGGER.warning("Invalid float for %s=%r; using %s.", name, raw_value, default)
        return default


def split_env(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


def safe_get_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
    source_name: str = "source",
) -> dict[str, Any] | list[Any] | None:
    """Execute a GET request and return parsed JSON, logging recoverable failures."""

    try:
        response = session.get(url, params=params, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        LOGGER.warning(
            "%s request failed for %s (%s)",
            source_name,
            _safe_url_for_log(url),
            type(exc).__name__,
        )
        return None
    except ValueError as exc:
        LOGGER.warning(
            "%s returned invalid JSON for %s (%s)",
            source_name,
            _safe_url_for_log(url),
            type(exc).__name__,
        )
        return None

    if not isinstance(payload, dict | list):
        LOGGER.warning("%s returned unexpected JSON payload type: %s", source_name, type(payload))
        return None
    return payload


def search_locations(global_filters: GlobalFilters | None) -> list[str]:
    if global_filters and global_filters.locations:
        return global_filters.locations
    return [""]


def limited_search_pairs(
    category_config: JobCategoryConfig,
    global_filters: GlobalFilters | None,
    max_queries: int,
) -> list[tuple[str, str]]:
    """Return title/location pairs capped to avoid accidental API overuse."""

    titles = category_config.search_titles or [category_config.category_name]
    locations = search_locations(global_filters)
    pairs: list[tuple[str, str]] = []

    for title in titles:
        for location in locations:
            pairs.append((title, location))
            if len(pairs) >= max_queries:
                return pairs
    return pairs


def category_query_text(category_config: JobCategoryConfig) -> str:
    parts = [category_config.category_name, *category_config.search_titles, *category_config.industries]
    return " ".join(clean_text(part).casefold() for part in parts if clean_text(part))


def matches_category(
    *,
    title: str,
    description: str,
    category_config: JobCategoryConfig,
) -> bool:
    """Return whether a source record appears related to a configured category."""

    haystack = clean_text(f"{title} {description}").casefold()
    if not haystack:
        return False

    title_terms = [term.casefold() for term in category_config.search_titles if term.strip()]
    industry_terms = [term.casefold() for term in category_config.industries if term.strip()]
    category_words = [word for word in category_config.category_name.casefold().split() if len(word) > 2]

    if any(term in haystack for term in title_terms):
        return True
    if any(term in haystack for term in industry_terms):
        return True
    return any(word in haystack for word in category_words)
