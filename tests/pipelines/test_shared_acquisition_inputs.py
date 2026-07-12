from __future__ import annotations

from pathlib import Path

from src.config.loader import build_config_snapshot, load_configs
from src.pipelines.shared_connector_refresh import (
    build_acquisition_inputs,
    build_acquisition_query_plan,
)


def _snapshot(
    *,
    user_uuid: str,
    locations: list[str],
    title: str,
    category_name: str = "User Search",
) -> dict[str, object]:
    snapshot = build_config_snapshot(
        {
            "jobs_config": {
                "revision": 2,
                "override_json": {
                    "global_filters": {
                        "country": "US",
                        "locations": locations,
                        "work_type": ["remote"],
                        "employment_type": ["full-time"],
                    },
                    "job_categories": [
                        {
                            "category_name": category_name,
                            "search_titles": [title],
                            "industries": ["technology"],
                            "seniority": ["Senior"],
                        }
                    ],
                },
            }
        }
    )
    return {"user_uuid": user_uuid, **snapshot}


def test_acquisition_inputs_union_all_active_user_job_configs() -> None:
    configs = load_configs(Path.cwd())
    filters, categories, metadata = build_acquisition_inputs(
        configs,
        [
            _snapshot(
                user_uuid="11111111-1111-4111-8111-111111111111",
                locations=["Seattle, WA"],
                title="Machine Learning Engineer",
            ),
            _snapshot(
                user_uuid="22222222-2222-4222-8222-222222222222",
                locations=["Austin, TX"],
                title="Analytics Engineer",
            ),
        ],
    )

    assert metadata["active_user_count"] == 2
    assert metadata["user_config_driven"] is True
    assert filters.locations == ["Seattle, WA", "Austin, TX"]
    assert [category.search_titles[0] for category in categories] == [
        "Machine Learning Engineer",
        "Analytics Engineer",
    ]


def test_empty_user_filter_broadens_shared_acquisition_for_that_field() -> None:
    configs = load_configs(Path.cwd())
    filters, _, _ = build_acquisition_inputs(
        configs,
        [
            _snapshot(
                user_uuid="11111111-1111-4111-8111-111111111111",
                locations=[],
                title="Data Scientist",
            ),
            _snapshot(
                user_uuid="22222222-2222-4222-8222-222222222222",
                locations=["Austin, TX"],
                title="Analytics Engineer",
            ),
        ],
    )

    assert filters.locations == []


def test_acquisition_inputs_fall_back_to_platform_config_without_active_users() -> None:
    configs = load_configs(Path.cwd())
    filters, categories, metadata = build_acquisition_inputs(configs, [])

    assert metadata["active_user_count"] == 0
    assert metadata["user_config_driven"] is False
    assert filters == configs.platform_connector.global_filters
    assert categories == list(configs.platform_connector.acquisition_categories)


def test_equivalent_user_acquisition_requests_share_one_query_key() -> None:
    configs = load_configs(Path.cwd())
    snapshots = [
        _snapshot(
            user_uuid="11111111-1111-4111-8111-111111111111",
            locations=["Seattle, WA"],
            title="Machine Learning Engineer",
        ),
        _snapshot(
            user_uuid="22222222-2222-4222-8222-222222222222",
            locations=["Seattle, WA"],
            title="Machine Learning Engineer",
        ),
    ]
    filters, categories, _ = build_acquisition_inputs(configs, snapshots)

    queries = build_acquisition_query_plan(
        source_names=["mock"],
        configs=configs,
        global_filters=filters,
        categories=categories,
        user_snapshots=snapshots,
    )

    assert len(queries) == 1
    assert queries[0]["interested_user_count"] == 2
    assert "user_uuid" not in queries[0]["request_json"]
