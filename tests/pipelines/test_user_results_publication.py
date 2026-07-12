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


class _Cursor:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self._row = row

    def fetchone(self) -> dict[str, object] | None:
        return self._row


class _Connection:
    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fail_on = fail_on
        self.statements: list[tuple[str, list[object]]] = []

    def execute(self, statement: str, params: list[object] | None = None) -> _Cursor:
        normalized = " ".join(statement.casefold().split())
        self.statements.append((normalized, list(params or [])))
        if self.fail_on and self.fail_on in normalized:
            raise RuntimeError("forced publication failure")
        if "from public.user_pipeline_runs" in normalized and "for update" in normalized:
            return _Cursor(
                {
                    "status": "running",
                    "user_uuid": USER_UUID,
                    "config_hash": CONFIG_HASH,
                }
            )
        return _Cursor()


class _Transaction:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def __enter__(self) -> _Connection:
        return self.connection

    def __exit__(self, *args: object) -> None:
        return None


class _Store:
    def __init__(self, connection: _Connection) -> None:
        self.connection = connection

    def transaction(self) -> _Transaction:
        return _Transaction(self.connection)


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


def test_publish_merges_touched_rows_without_clearing_user_dataset() -> None:
    connection = _Connection()

    result = UserResultsPublisher(store=_Store(connection)).publish(
        user_uuid=USER_UUID,
        run_uuid=RUN_UUID,
        config_hash=CONFIG_HASH,
        jobs_considered=1,
        matches=[
            {
                "user_uuid": USER_UUID,
                "run_uuid": RUN_UUID,
                "job_id": "job-101",
                "category_name": "Analytics Engineer",
                "match_score": 91,
                "matched_skills": ["SQL"],
                "missing_skills": [],
                "ranking_reasons": ["Strong SQL match"],
                "is_top_match": True,
            }
        ],
        category_summary=[
            {
                "user_uuid": USER_UUID,
                "run_uuid": RUN_UUID,
                "category_name": "Analytics Engineer",
                "metrics": {"jobs_found": 1},
            }
        ],
        skill_gap=[],
        company_priority=[],
    )

    statements = "\n".join(statement for statement, _ in connection.statements)

    assert result["jobs_matched"] == 1
    assert "set is_current = false where user_uuid = %s and is_current = true" not in statements
    assert "and job_id = %s and is_current = true" in statements
    assert "on conflict (user_uuid, job_id, run_uuid) do update" in statements
    assert "superseded_by_personal_refresh" in statements
    assert "shared_job_inactive" in statements


def test_noop_publish_leaves_existing_current_rows_untouched() -> None:
    connection = _Connection()

    UserResultsPublisher(store=_Store(connection)).publish(
        user_uuid=USER_UUID,
        run_uuid=RUN_UUID,
        config_hash=CONFIG_HASH,
        jobs_considered=0,
        matches=[],
        category_summary=[],
        skill_gap=[],
        company_priority=[],
    )

    statements = "\n".join(statement for statement, _ in connection.statements)

    assert "superseded_by_personal_refresh" not in statements
    assert "delete from public.user_job_matches where user_uuid = %s and run_uuid = %s and is_current = false" in statements
    assert "shared_job_inactive" in statements


def test_failed_publish_never_uses_global_user_result_clear() -> None:
    connection = _Connection(fail_on="insert into public.user_job_matches")

    with pytest.raises(RuntimeError, match="forced publication failure"):
        UserResultsPublisher(store=_Store(connection)).publish(
            user_uuid=USER_UUID,
            run_uuid=RUN_UUID,
            config_hash=CONFIG_HASH,
            jobs_considered=1,
            matches=[
                {
                    "user_uuid": USER_UUID,
                    "run_uuid": RUN_UUID,
                    "job_id": "job-50",
                    "category_name": "Analytics Engineer",
                    "match_score": 88,
                }
            ],
            category_summary=[],
            skill_gap=[],
            company_priority=[],
        )

    statements = "\n".join(statement for statement, _ in connection.statements)

    assert "set is_current = false where user_uuid = %s and is_current = true" not in statements
