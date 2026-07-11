from __future__ import annotations

import pytest

from packages.careersignal_core.publication.user_results import (
    RESULT_TABLES,
    UserResultPublicationError,
    UserResultsPublisher,
    _normalize_result_value,
)

USER_UUID = "11111111-1111-4111-8111-111111111111"
RUN_UUID = "22222222-2222-4222-8222-222222222222"
OTHER_USER_UUID = "33333333-3333-4333-8333-333333333333"
CONFIG_HASH = "snapshot-hash"


def test_result_normalization_converts_nan_to_database_null() -> None:
    normalized = _normalize_result_value(
        {"preferred_skill_score": float("nan"), "metrics": [1.0, float("inf")]}
    )

    assert normalized == {"preferred_skill_score": None, "metrics": [1.0, None]}


def _empty_results() -> dict[str, list[dict[str, object]]]:
    return {table: [] for table in RESULT_TABLES}


def test_publish_user_results_rejects_foreign_summary_uuid_before_adapting() -> None:
    results = _empty_results()
    results["mart_category_summary"] = [
        {
            "user_uuid": OTHER_USER_UUID,
            "run_uuid": RUN_UUID,
            "category_name": "Analytics Engineer",
            "jobs_found": 3,
            "config_hash": CONFIG_HASH,
        }
    ]

    with pytest.raises(UserResultPublicationError, match="foreign user UUID"):
        UserResultsPublisher(store=object()).publish_user_results(
            user_uuid=USER_UUID,
            run_uuid=RUN_UUID,
            config_hash=CONFIG_HASH,
            results=results,
        )


def test_publish_user_results_preserves_valid_user_context_in_adapter() -> None:
    captured: dict[str, object] = {}

    class CapturingPublisher(UserResultsPublisher):
        def publish(self, **kwargs: object) -> dict[str, int]:
            captured.update(kwargs)
            return {"jobs_considered": 0, "jobs_matched": 0, "category_rows": 1}

    results = _empty_results()
    results["mart_category_summary"] = [
        {
            "user_uuid": USER_UUID,
            "run_uuid": RUN_UUID,
            "category_name": "Analytics Engineer",
            "jobs_found": 3,
            "config_hash": CONFIG_HASH,
        }
    ]

    CapturingPublisher(store=object()).publish_user_results(
        user_uuid=USER_UUID,
        run_uuid=RUN_UUID,
        config_hash=CONFIG_HASH,
        results=results,
    )

    assert captured["user_uuid"] == USER_UUID
    assert captured["run_uuid"] == RUN_UUID
    assert captured["category_summary"] == [
        {
            "user_uuid": USER_UUID,
            "run_uuid": RUN_UUID,
            "category_name": "Analytics Engineer",
            "metrics": {"jobs_found": 3, "config_hash": CONFIG_HASH},
        }
    ]
