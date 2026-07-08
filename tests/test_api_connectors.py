from __future__ import annotations

from typing import Any

from src.config.loader import load_configs
from src.connectors.adzuna_connector import AdzunaConnector
from src.connectors.greenhouse_connector import GreenhouseConnector
from src.connectors.lever_connector import LeverConnector
from src.connectors.serpapi_connector import SerpApiConnector
from src.connectors.usajobs_connector import USAJobsConnector


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | list[Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any] | list[Any]:
        return self.payload


class FakeSession:
    def __init__(self, payloads: list[dict[str, Any] | list[Any]]) -> None:
        self.payloads = payloads
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "params": params or {},
                "headers": headers or {},
                "timeout": timeout,
            }
        )
        return FakeResponse(self.payloads.pop(0))


def _category(name: str = "Data Scientist - Tech"):
    configs = load_configs(".")
    return next(category for category in configs.jobs.job_categories if category.category_name == name)


def test_adzuna_connector_maps_results(monkeypatch) -> None:
    monkeypatch.setenv("ADZUNA_MAX_QUERIES_PER_CATEGORY", "1")
    session = FakeSession(
        [
            {
                "results": [
                    {
                        "id": "adz-1",
                        "title": "Product Data Scientist",
                        "company": {"display_name": "NimbusAI"},
                        "location": {"display_name": "Remote"},
                        "category": {"label": "IT Jobs"},
                        "salary_min": 130000,
                        "salary_max": 170000,
                        "created": "2026-07-08T10:00:00Z",
                        "redirect_url": "https://adzuna.example/job/1",
                        "description": "Python SQL product analytics role.",
                    }
                ]
            }
        ]
    )
    connector = AdzunaConnector(
        app_id="id",
        app_key="key",
        global_filters=load_configs(".").jobs.global_filters,
        session=session,  # type: ignore[arg-type]
    )

    jobs = connector.fetch_jobs(_category())

    assert jobs[0]["source"] == "adzuna"
    assert jobs[0]["title"] == "Product Data Scientist"
    assert jobs[0]["company"] == "NimbusAI"
    assert jobs[0]["salary"] == "130000 - 170000"
    assert session.calls[0]["params"]["app_id"] == "id"


def test_serpapi_connector_maps_google_jobs_results(monkeypatch) -> None:
    monkeypatch.setenv("SERPAPI_MAX_QUERIES_PER_CATEGORY", "1")
    session = FakeSession(
        [
            {
                "jobs_results": [
                    {
                        "job_id": "serp-1",
                        "title": "Senior BI Analyst",
                        "company_name": "First Harbor Bank",
                        "location": "Wilmington, DE",
                        "via": "LinkedIn",
                        "share_link": "https://google.example/job/1",
                        "description": "SQL and Power BI dashboards.",
                        "extensions": ["Full-time", "$110,000 - $135,000"],
                        "detected_extensions": {
                            "posted_at": "2 days ago",
                            "schedule_type": "Full-time",
                        },
                        "apply_options": [
                            {"title": "LinkedIn", "link": "https://apply.example/job/1"}
                        ],
                    }
                ]
            }
        ]
    )
    connector = SerpApiConnector(
        api_key="key",
        global_filters=load_configs(".").jobs.global_filters,
        session=session,  # type: ignore[arg-type]
    )

    jobs = connector.fetch_jobs(_category("BI Analyst - Banking"))

    assert jobs[0]["source"] == "serpapi_google_jobs"
    assert jobs[0]["apply_link"] == "https://apply.example/job/1"
    assert jobs[0]["salary"] == "$110,000 - $135,000"
    assert session.calls[0]["params"]["engine"] == "google_jobs"


def test_greenhouse_connector_fetches_board_and_filters_category() -> None:
    session = FakeSession(
        [
            {
                "jobs": [
                    {
                        "id": 123,
                        "title": "Healthcare Analytics Engineer",
                        "absolute_url": "https://boards.greenhouse.io/medmetric/jobs/123",
                        "updated_at": "2026-07-08T12:00:00Z",
                        "location": {"name": "Philadelphia, PA"},
                        "departments": [{"name": "Data"}],
                        "content": "SQL Python dbt healthcare analytics dashboards.",
                    }
                ]
            }
        ]
    )
    connector = GreenhouseConnector(
        company_tokens=["medmetric"],
        session=session,  # type: ignore[arg-type]
    )

    jobs = connector.fetch_jobs(_category("Healthcare Analytics Engineer"))

    assert jobs[0]["source"] == "greenhouse"
    assert jobs[0]["company"] == "medmetric"
    assert jobs[0]["date_posted"] == "2026-07-08"
    assert jobs[0]["category_name"] == "Healthcare Analytics Engineer"


def test_lever_connector_fetches_site_and_filters_category() -> None:
    session = FakeSession(
        [
            [
                {
                    "id": "lever-1",
                    "text": "Analytics Engineer",
                    "hostedUrl": "https://jobs.lever.co/signalworks/1",
                    "applyUrl": "https://jobs.lever.co/signalworks/1/apply",
                    "createdAt": 1783507200000,
                    "categories": {
                        "team": "Data",
                        "location": "Remote",
                        "commitment": "Full-time",
                    },
                    "content": {
                        "description": "Build dbt models and metric layers.",
                        "lists": [{"text": "Requirements", "content": "SQL Python dbt"}],
                    },
                    "salaryRange": {"min": 125000, "max": 165000, "currency": "USD"},
                }
            ]
        ]
    )
    connector = LeverConnector(
        company_sites=["signalworks"],
        session=session,  # type: ignore[arg-type]
    )

    jobs = connector.fetch_jobs(_category("Analytics Engineer"))

    assert jobs[0]["source"] == "lever"
    assert jobs[0]["salary"] == "USD 125000 - 165000"
    assert jobs[0]["apply_link"] == "https://jobs.lever.co/signalworks/1/apply"


def test_usajobs_connector_maps_search_results(monkeypatch) -> None:
    monkeypatch.setenv("USAJOBS_MAX_QUERIES_PER_CATEGORY", "1")
    session = FakeSession(
        [
            {
                "SearchResult": {
                    "SearchResultItems": [
                        {
                            "MatchedObjectId": "fed-1",
                            "MatchedObjectDescriptor": {
                                "PositionID": "fed-1",
                                "PositionTitle": "Data Scientist",
                                "OrganizationName": "Centers for Medicare & Medicaid Services",
                                "PositionLocationDisplay": "Washington, DC",
                                "PositionURI": "https://www.usajobs.gov/job/fed-1",
                                "ApplyURI": ["https://apply.usastaffing.gov/fed-1"],
                                "PublicationStartDate": "2026-07-08",
                                "PositionSchedule": [{"Name": "Full-time"}],
                                "PositionRemuneration": [
                                    {
                                        "MinimumRange": "120000",
                                        "MaximumRange": "155000",
                                        "RateIntervalCode": "Per Year",
                                    }
                                ],
                                "UserArea": {
                                    "Details": {
                                        "JobSummary": "Healthcare data science role.",
                                        "MajorDuties": "Use Python and SQL.",
                                        "Requirements": "Analytics experience.",
                                    }
                                },
                            },
                        }
                    ]
                }
            }
        ]
    )
    connector = USAJobsConnector(
        api_key="key",
        user_agent="user@example.com",
        global_filters=load_configs(".").jobs.global_filters,
        session=session,  # type: ignore[arg-type]
    )

    jobs = connector.fetch_jobs(_category("Data Scientist - Healthcare"))

    assert jobs[0]["source"] == "usajobs"
    assert jobs[0]["company"] == "Centers for Medicare & Medicaid Services"
    assert jobs[0]["apply_link"] == "https://apply.usastaffing.gov/fed-1"
    assert session.calls[0]["headers"]["Authorization-Key"] == "key"
