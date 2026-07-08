"""Discover public Greenhouse and Lever board identifiers from career URLs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests

from src.utils.text_cleaning import clean_text

GREENHOUSE_HOSTS = {"boards.greenhouse.io", "boards-api.greenhouse.io"}
LEVER_HOSTS = {
    "jobs.lever.co",
    "api.lever.co",
    "jobs.eu.lever.co",
    "api.eu.lever.co",
}
USER_AGENT = "CareerSignal ATS board discovery (+https://github.com/local/careersignal)"

GREENHOUSE_PATTERNS = (
    re.compile(r"https?://boards\.greenhouse\.io/([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(
        r"https?://boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)",
        re.IGNORECASE,
    ),
    re.compile(r"greenhouse\.io/embed/job_board\?for=([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"greenhouse(?:[^\"'<>\s]{0,120})[?&]for=([A-Za-z0-9_-]+)", re.IGNORECASE),
)

LEVER_PATTERNS = (
    re.compile(r"https?://jobs(?:\.eu)?\.lever\.co/([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"https?://api(?:\.eu)?\.lever\.co/v0/postings/([A-Za-z0-9_-]+)", re.IGNORECASE),
)


@dataclass(frozen=True)
class BoardValidation:
    source: str
    identifier: str
    is_valid: bool
    job_count: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BoardDiscoveryResult:
    company_name: str
    source_url: str
    final_url: str
    greenhouse_tokens: list[str]
    lever_sites: list[str]
    validations: list[BoardValidation]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["validations"] = [validation.to_dict() for validation in self.validations]
        return data


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(set(value.strip() for value in values if value.strip()), key=str.casefold)


def _normalize_identifier(value: str) -> str:
    return unquote(clean_text(value)).strip().strip("/")


def _is_placeholder(value: str) -> bool:
    return value.casefold() in {
        "jobs",
        "embed",
        "v1",
        "boards",
        "postings",
        "assets",
        "static",
        "favicon.ico",
    }


def extract_greenhouse_tokens(text: str) -> list[str]:
    """Extract Greenhouse board tokens from URLs, embeds, and API links."""

    tokens: list[str] = []
    for pattern in GREENHOUSE_PATTERNS:
        tokens.extend(_normalize_identifier(match) for match in pattern.findall(text))

    single_url = text.strip()
    parsed = urlparse(single_url) if re.fullmatch(r"https?://\S+", single_url) else urlparse("")
    if parsed.netloc.casefold() in GREENHOUSE_HOSTS:
        if parsed.path.startswith("/embed/job_board"):
            token = parse_qs(parsed.query).get("for", [""])[0]
            if token:
                tokens.append(_normalize_identifier(token))
        else:
            path_parts = [part for part in parsed.path.split("/") if part]
            if parsed.netloc.casefold() == "boards.greenhouse.io" and path_parts:
                tokens.append(_normalize_identifier(path_parts[0]))
            if parsed.netloc.casefold() == "boards-api.greenhouse.io":
                try:
                    boards_index = path_parts.index("boards")
                    tokens.append(_normalize_identifier(path_parts[boards_index + 1]))
                except (ValueError, IndexError):
                    pass

    return _unique_sorted([token for token in tokens if not _is_placeholder(token)])


def extract_lever_sites(text: str) -> list[str]:
    """Extract Lever site names from hosted job-site and API URLs."""

    sites: list[str] = []
    for pattern in LEVER_PATTERNS:
        sites.extend(_normalize_identifier(match) for match in pattern.findall(text))

    single_url = text.strip()
    parsed = urlparse(single_url) if re.fullmatch(r"https?://\S+", single_url) else urlparse("")
    if parsed.netloc.casefold() in LEVER_HOSTS:
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.netloc.casefold().startswith("jobs.") and path_parts:
            sites.append(_normalize_identifier(path_parts[0]))
        if parsed.netloc.casefold().startswith("api."):
            try:
                postings_index = path_parts.index("postings")
                sites.append(_normalize_identifier(path_parts[postings_index + 1]))
            except (ValueError, IndexError):
                pass

    return _unique_sorted([site for site in sites if not _is_placeholder(site)])


class ATSBoardDiscoverer:
    """Discovers and validates public Greenhouse/Lever identifiers."""

    def __init__(
        self,
        session: requests.Session | None = None,
        timeout: float = 15.0,
        validate: bool = True,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout = timeout
        self.validate = validate

    def discover(self, source_url: str, company_name: str = "") -> BoardDiscoveryResult:
        errors: list[str] = []
        final_url = source_url
        text_parts = [source_url]

        try:
            response = self.session.get(
                source_url,
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
                allow_redirects=True,
            )
            response.raise_for_status()
            final_url = getattr(response, "url", source_url) or source_url
            text_parts.extend([final_url, getattr(response, "text", "") or ""])
        except requests.RequestException as exc:
            errors.append(f"Unable to fetch {source_url}: {exc}")

        joined_text = "\n".join(text_parts)
        greenhouse_tokens = extract_greenhouse_tokens(joined_text)
        lever_sites = extract_lever_sites(joined_text)

        validations: list[BoardValidation] = []
        if self.validate:
            validations.extend(self.validate_greenhouse_token(token) for token in greenhouse_tokens)
            validations.extend(self.validate_lever_site(site) for site in lever_sites)

        return BoardDiscoveryResult(
            company_name=company_name,
            source_url=source_url,
            final_url=final_url,
            greenhouse_tokens=greenhouse_tokens,
            lever_sites=lever_sites,
            validations=validations,
            errors=errors,
        )

    def validate_greenhouse_token(self, token: str) -> BoardValidation:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        try:
            response = self.session.get(
                url,
                params={"content": "true"},
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return BoardValidation("greenhouse", token, False, error=str(exc))

        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        if isinstance(jobs, list):
            return BoardValidation("greenhouse", token, True, job_count=len(jobs))
        return BoardValidation("greenhouse", token, False, error="Unexpected Greenhouse response")

    def validate_lever_site(self, site: str) -> BoardValidation:
        url = f"https://api.lever.co/v0/postings/{site}"
        try:
            response = self.session.get(
                url,
                params={"mode": "json"},
                timeout=self.timeout,
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            return BoardValidation("lever", site, False, error=str(exc))

        if isinstance(payload, list):
            return BoardValidation("lever", site, True, job_count=len(payload))
        return BoardValidation("lever", site, False, error="Unexpected Lever response")
