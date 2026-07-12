from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from apps.api.dependencies.authorization import require_active_user, require_non_demo_user
from apps.api.dependencies.models import CurrentUser
from apps.api.dependencies.preferences import get_preferences_service
from apps.api.main import app
from packages.careersignal_core.preferences.compiler import PreferencesCompiler
from packages.careersignal_core.preferences.models import (
    CompensationPreferences,
    MatchPriorities,
    PreferencesDocument,
    PreferencesPayload,
    SearchPreferences,
    SkillPreference,
)
from packages.careersignal_core.preferences.reverse_mapping import reverse_map_legacy_configs
from packages.careersignal_core.preferences.skill_aliases import SkillAliasService
from packages.careersignal_core.preferences.title_expansion import expand_job_title
from src.config.loader import CONFIG_TYPES, load_default_config, validate_user_config


USER_UUID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_USER_UUID = "22222222-2222-4222-8222-222222222222"


def _payload() -> PreferencesPayload:
    return PreferencesPayload(
        search_preferences=SearchPreferences(
            job_titles=["Senior Data Analyst", "Registered Nurse"],
            industries=["Financial Services", "Healthcare"],
            seniority=["Senior"],
            country="United States",
            locations=[" New York, NY ", "Remote"],
            work_arrangements=["Remote", "Hybrid"],
            employment_types=["Full-time", "Contract"],
            visa_preferences=["Sponsorship required"],
            excluded_companies=[" Example Corp "],
            excluded_titles=["Intern"],
            compensation=CompensationPreferences(
                minimum_salary=100_000,
                preferred_salary=135_000,
                currency="usd",
                period="annual",
            ),
        ),
        skills=[
            SkillPreference(name="Power BI", category="Business Intelligence"),
            SkillPreference(name="Registered Nursing"),
        ],
        skill_categories=["Business Intelligence"],
        match_priorities=MatchPriorities(
            title_match=25,
            required_skill_match=30,
            industry_match=15,
            salary_match=10,
            work_arrangement_match=10,
            visa_signal_match=10,
        ),
    )


def test_preferences_validation_normalizes_safe_values_and_rejects_bad_totals() -> None:
    payload = _payload()

    assert payload.search_preferences.country == "US"
    assert payload.search_preferences.compensation.currency == "USD"
    assert payload.search_preferences.work_arrangements == ["remote", "hybrid"]
    assert payload.search_preferences.employment_types == ["full_time", "contract"]
    assert payload.search_preferences.excluded_companies == ["Example Corp"]

    sanitized = SkillPreference(name="<script>alert(1)</script>  Clinical   Operations")
    assert sanitized.name == "alert(1) Clinical Operations"

    with pytest.raises(ValidationError, match="total exactly 100"):
        MatchPriorities(title_match=99)

    with pytest.raises(ValidationError, match="cannot be below"):
        CompensationPreferences(minimum_salary=100, preferred_salary=99)


@pytest.mark.parametrize(
    ("title", "expected_variant"),
    [
        ("Senior Data Analyst", "Sr. Data Analyst"),
        ("Registered Nurse", "RN"),
        ("Mechanical Engineer", "Mechanical Engineer"),
        ("Product Manager", "Product Manager"),
        ("Corporate Counsel", "Corporate Counsel"),
        ("Operations Manager", "Operations Manager"),
    ],
)
def test_title_generation_is_deterministic_and_profession_agnostic(
    title: str,
    expected_variant: str,
) -> None:
    first = expand_job_title(title)
    second = expand_job_title(title)

    assert first == second
    assert first[0] == title
    assert expected_variant in first
    assert len({value.casefold() for value in first}) == len(first)


def test_skill_alias_generation_reuses_catalog_and_deduplicates() -> None:
    aliases = SkillAliasService().generate(
        [SkillPreference(name="Power BI", category="Business Intelligence")],
        catalog={
            "power bi": [
                {"alias": "PBI", "confidence": 0.95},
                {"alias": "PowerBI", "confidence": 0.95},
            ]
        },
    )[0]

    assert aliases.source == "catalog"
    assert aliases.confidence == 0.95
    assert {"Power BI", "PowerBI", "Microsoft Power BI", "PBI"}.issubset(aliases.aliases)
    assert len({value.casefold() for value in aliases.aliases}) == len(aliases.aliases)


def test_compiler_derives_all_legacy_configs_and_validates_strict_schemas() -> None:
    compiled = PreferencesCompiler().compile(_payload())
    configs = compiled["effective_configs"]

    assert set(configs) == set(CONFIG_TYPES)
    for config_type in CONFIG_TYPES:
        assert validate_user_config(config_type, configs[config_type]) == configs[config_type]

    candidate = configs["candidate_profile"]["candidate"]
    jobs = configs["jobs_config"]
    taxonomy = configs["skill_taxonomy"]["skill_aliases"]
    assert candidate["target_titles"] == ["Senior Data Analyst", "Registered Nurse"]
    assert candidate["target_industries"] == ["Financial Services", "Healthcare"]
    assert candidate["required_preferences"]["work_arrangement"] == ["remote", "hybrid"]
    assert candidate["salary_expectation"] == {
        "min_base_salary": 100_000,
        "preferred_base_salary": 135_000,
    }
    assert candidate["skills"]["general"] == ["Registered Nursing"]
    assert jobs["global_filters"]["locations"] == ["New York, NY", "Remote"]
    assert jobs["global_filters"]["visa_preferences"] == ["sponsorship_required"]
    assert jobs["ranking_weights"]["required_skill_match"] == 0.30
    assert jobs["output"]["excel_file"] == "outputs/job_search_tracker.xlsx"
    assert any(value["canonical"] == "Power BI" and "PBI" in value["aliases"] for value in taxonomy.values())
    assert compiled["generated_preview"].search_titles[0].variations[0] == "Senior Data Analyst"


def test_reverse_mapping_preserves_existing_configured_preferences() -> None:
    compiled = PreferencesCompiler().compile(_payload())

    preferences, preview, warnings = reverse_map_legacy_configs(
        compiled["effective_configs"],
        confirmed=True,
    )

    search = preferences.search_preferences
    assert search.job_titles == ["Senior Data Analyst", "Registered Nurse"]
    assert search.industries == ["Financial Services", "Healthcare"]
    assert search.locations == ["New York, NY", "Remote"]
    assert search.work_arrangements == ["remote", "hybrid"]
    assert search.compensation.minimum_salary == 100_000
    assert {skill.name for skill in preferences.skills}.issuperset({"Power BI", "Registered Nursing"})
    assert sum(preferences.match_priorities.model_dump().values()) == 100
    assert preview.search_titles
    assert any("legacy" in warning.casefold() for warning in warnings)


def _current_user() -> CurrentUser:
    return CurrentUser(
        user_uuid=USER_UUID,
        username="preferences-test",
        role="user",
        account_status="active",
        created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        activated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        expires_at=None,
        remaining_days=None,
        last_successful_pipeline_run_uuid=None,
    )


class FakePreferencesService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.saved_payload: PreferencesPayload | None = None

    def get_preferences(self, user_uuid: UUID) -> PreferencesDocument:
        self.user_ids.append(str(user_uuid))
        payload = _payload()
        return PreferencesDocument(**payload.model_dump(), profile_completeness=100)

    def options(self, *, kind: str | None, query: str, limit: int, offset: int) -> dict[str, Any]:
        self.user_ids.append("options-authenticated")
        return {
            "countries": [{"value": "US", "label": "United States"}],
            "locations": [{"value": "New York, NY", "label": "New York, NY"}] if kind == "locations" else [],
            "industries": [],
            "seniority_levels": [],
            "employment_types": [],
            "work_arrangements": [],
            "visa_options": [],
            "companies": [],
            "job_titles": [],
            "pagination": {
                "kind": kind,
                "query": query,
                "limit": limit,
                "offset": offset,
                "total": 1,
                "has_more": False,
            } if kind else None,
        }

    def save_preferences(
        self,
        user_uuid: UUID,
        preferences: PreferencesPayload,
        **_: Any,
    ) -> PreferencesDocument:
        self.user_ids.append(str(user_uuid))
        self.saved_payload = preferences
        return PreferencesDocument(**preferences.model_dump(), profile_completeness=100)


def test_preferences_api_uses_authenticated_identity_and_paginates_shared_options() -> None:
    service = FakePreferencesService()
    app.dependency_overrides[require_active_user] = _current_user
    app.dependency_overrides[require_non_demo_user] = _current_user
    app.dependency_overrides[get_preferences_service] = lambda: service
    client = TestClient(app)
    try:
        loaded = client.get("/api/preferences")
        options = client.get(
            "/api/preferences/options",
            params={"kind": "locations", "q": "new", "limit": 10, "offset": 0},
        )
        saved = client.put("/api/preferences", json=_payload().model_dump(mode="json"))
        injected = client.put(
            "/api/preferences",
            json={**_payload().model_dump(mode="json"), "user_uuid": OTHER_USER_UUID},
        )
    finally:
        app.dependency_overrides.clear()

    assert loaded.status_code == 200
    assert options.status_code == 200
    assert options.json()["pagination"]["query"] == "new"
    assert saved.status_code == 200
    assert service.saved_payload is not None
    assert service.user_ids.count(str(USER_UUID)) == 2
    assert OTHER_USER_UUID not in service.user_ids
    assert injected.status_code == 422


def test_repository_defaults_remain_valid_for_reverse_mapping_fallback() -> None:
    defaults = {config_type: load_default_config(config_type) for config_type in CONFIG_TYPES}
    preferences, _, _ = reverse_map_legacy_configs(defaults, confirmed=False)

    assert preferences.search_preferences.job_titles
    assert sum(preferences.match_priorities.model_dump().values()) == 100
