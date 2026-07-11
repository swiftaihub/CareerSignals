from __future__ import annotations

from copy import deepcopy

import pytest

from src.config.loader import (
    CONFIG_TYPES,
    ConfigLoadError,
    build_config_snapshot,
    effective_config_hash,
    load_default_config,
    merge_config,
    validate_user_config,
)


def test_empty_overrides_produce_exact_validated_defaults() -> None:
    snapshot = build_config_snapshot({})

    assert tuple(snapshot["configs"]) == CONFIG_TYPES
    for config_type in CONFIG_TYPES:
        assert snapshot["configs"][config_type] == load_default_config(config_type)


def test_recursive_merge_is_detached_and_changes_only_requested_field() -> None:
    default = load_default_config("candidate_profile")
    original = deepcopy(default)
    override = {"candidate": {"salary_expectation": {"min_base_salary": 130000}}}

    merged = merge_config(default, override)

    assert default == original
    assert merged["candidate"]["salary_expectation"]["min_base_salary"] == 130000
    assert (
        merged["candidate"]["salary_expectation"]["preferred_base_salary"]
        == default["candidate"]["salary_expectation"]["preferred_base_salary"]
    )


def test_user_jobs_rejects_platform_connector_fields() -> None:
    jobs = load_default_config("jobs_config")
    jobs["freshness_filter"] = {"enabled": False, "max_post_age_hours": 72}

    with pytest.raises(ConfigLoadError, match="freshness_filter"):
        validate_user_config("jobs_config", jobs)


def test_snapshot_hash_and_revisions_are_deterministic_and_detached() -> None:
    override = {
        "candidate_profile": {
            "override_json": {
                "candidate": {"salary_expectation": {"min_base_salary": 125000}}
            },
            "revision": 7,
        }
    }
    snapshot = build_config_snapshot(override)
    same_snapshot = build_config_snapshot(deepcopy(override))

    assert snapshot == same_snapshot
    assert snapshot["config_revision_map"]["candidate_profile"] == 7
    body = {key: value for key, value in snapshot.items() if key != "config_hash"}
    assert snapshot["config_hash"] == effective_config_hash(body)

    override["candidate_profile"]["override_json"]["candidate"]["salary_expectation"][
        "min_base_salary"
    ] = 1
    assert (
        snapshot["configs"]["candidate_profile"]["candidate"]["salary_expectation"][
            "min_base_salary"
        ]
        == 125000
    )


def test_unknown_config_type_is_rejected() -> None:
    with pytest.raises(ConfigLoadError, match="Unsupported config type"):
        load_default_config("platform_connector_config")
