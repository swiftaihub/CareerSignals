from __future__ import annotations

from typing import Any

from src.discovery.ats_boards import (
    ATSBoardDiscoverer,
    extract_greenhouse_tokens,
    extract_lever_sites,
)


class FakeResponse:
    def __init__(self, payload: Any, url: str = "https://example.com/careers") -> None:
        self._payload = payload
        self.url = url
        self.text = payload if isinstance(payload, str) else ""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        if "boards-api.greenhouse.io" in url:
            return FakeResponse({"jobs": [{"id": 1}, {"id": 2}]}, url=url)
        if "api.lever.co" in url:
            return FakeResponse([{"id": "abc"}], url=url)
        return FakeResponse(
            """
            <a href="https://boards.greenhouse.io/vaulttec/jobs/127817">Job</a>
            <a href="https://jobs.lever.co/leverdemo">Lever jobs</a>
            <script src="https://boards.greenhouse.io/embed/job_board?for=sampleco"></script>
            """,
            url="https://example.com/careers",
        )


def test_extract_greenhouse_tokens_from_common_url_shapes() -> None:
    text = """
    https://boards.greenhouse.io/vaulttec/jobs/127817
    https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true
    https://boards.greenhouse.io/embed/job_board?for=embeddedco
    """

    assert extract_greenhouse_tokens(text) == ["acme", "embeddedco", "vaulttec"]


def test_extract_lever_sites_from_common_url_shapes() -> None:
    text = """
    https://jobs.lever.co/leverdemo
    https://api.lever.co/v0/postings/acme?mode=json
    https://jobs.eu.lever.co/eucompany/123
    """

    assert extract_lever_sites(text) == ["acme", "eucompany", "leverdemo"]


def test_discoverer_finds_and_validates_greenhouse_and_lever() -> None:
    discoverer = ATSBoardDiscoverer(session=FakeSession())

    result = discoverer.discover("https://example.com/careers", company_name="Example")

    assert result.company_name == "Example"
    assert result.greenhouse_tokens == ["sampleco", "vaulttec"]
    assert result.lever_sites == ["leverdemo"]
    assert all(validation.is_valid for validation in result.validations)
