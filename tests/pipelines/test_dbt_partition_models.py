from __future__ import annotations

from pathlib import Path

import yaml


def test_user_models_require_context_and_exact_partition_hook() -> None:
    user_models = []
    for path in Path("dbt/models").rglob("*.sql"):
        sql = path.read_text(encoding="utf-8")
        if "tags=['user'" in sql:
            user_models.append(path)
            assert "require_user_context()" in sql, path
            assert "user_uuid" in sql and "run_uuid" in sql, path
            assert "delete_user_partition()" in sql, path

    assert user_models


def test_no_model_contains_unqualified_delete_or_truncate() -> None:
    for path in Path("dbt/models").rglob("*.sql"):
        normalized = " ".join(path.read_text(encoding="utf-8").lower().split())
        assert "truncate table" not in normalized, path
        assert "delete from {{ this }}" not in normalized, path


def test_shared_models_are_scoped_to_the_current_connector_run() -> None:
    shared_models = [
        Path("dbt/models/staging/stg_job_posts.sql"),
        Path("dbt/models/intermediate/int_job_posts_deduped.sql"),
        Path("dbt/models/marts/mart_shared_canonical_jobs.sql"),
        Path("dbt/models/marts/mart_shared_source_freshness.sql"),
    ]

    for path in shared_models:
        sql = path.read_text(encoding="utf-8")
        assert "validate_shared_context()" in sql, path
        assert "purge_unscoped_shared_rows()" in sql, path

    staging_sql = shared_models[0].read_text(encoding="utf-8")
    assert "var('connector_run_uuid', none)" in staging_sql
    assert "and connector_run_uuid = '{{ connector_run_uuid }}'" in staging_sql

    macro_sql = Path("dbt/macros/delete_user_partition.sql").read_text(
        encoding="utf-8"
    )
    assert "connector_run_uuid != '{{ connector_run_uuid }}'" in macro_sql


def test_user_shared_relationship_test_is_scoped_to_current_partition() -> None:
    schema = yaml.safe_load(
        Path("dbt/models/marts/schema.yml").read_text(encoding="utf-8")
    )
    scored_model = next(
        model for model in schema["models"] if model["name"] == "mart_jobs_scored"
    )
    job_id_column = next(
        column for column in scored_model["columns"] if column["name"] == "job_id"
    )

    # Historical user/run partitions outlive the current shared connector
    # snapshot, so a generic full-table relationship test is not a valid
    # invariant for mart_jobs_scored.
    assert not any(
        isinstance(data_test, dict) and "relationships" in data_test
        for data_test in job_id_column["data_tests"]
    )

    relationship_test = Path(
        "dbt/tests/assert_user_result_references_shared_job.sql"
    ).read_text(encoding="utf-8")
    assert "require_user_context()" in relationship_test
    assert "config(tags=['user'])" in relationship_test
    assert "results.user_uuid = '{{ var(\"user_uuid\") }}'" in relationship_test
    assert "results.run_uuid = '{{ var(\"run_uuid\") }}'" in relationship_test
    assert "shared.job_id is null" in relationship_test
