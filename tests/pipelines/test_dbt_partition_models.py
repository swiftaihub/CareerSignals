from __future__ import annotations

from pathlib import Path


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
