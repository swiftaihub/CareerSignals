from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import pytest

from packages.careersignal_core.repositories.configs import _coherent_bundle_uuid
from packages.careersignal_core.repositories.errors import (
    ConfigBundleConflictError,
    PipelineDailyLimitError,
)
from packages.careersignal_core.repositories.preferences import PreferencesRepository
from packages.careersignal_core.repositories.pipeline_runs import (
    PipelineRunRepository,
    pipeline_quota_window,
)
from src.config.loader import CONFIG_TYPES, build_config_snapshot


USER_UUID = "11111111-1111-4111-8111-111111111111"
ACTOR_UUID = "22222222-2222-4222-8222-222222222222"
OLD_BUNDLE_UUID = "33333333-3333-4333-8333-333333333333"


class Cursor:
    def __init__(
        self,
        *,
        one: dict[str, Any] | None = None,
        all_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.one = one
        self.all_rows = all_rows or []

    def fetchone(self) -> dict[str, Any] | None:
        return self.one

    def fetchall(self) -> list[dict[str, Any]]:
        return self.all_rows


class BundleConnection:
    def __init__(self, *, fail_config_type: str | None = None) -> None:
        self.fail_config_type = fail_config_type
        self.documents = {
            config_type: {"revision": 2, "bundle_revision_uuid": OLD_BUNDLE_UUID}
            for config_type in CONFIG_TYPES
        }
        self.version_rows: list[dict[str, Any]] = []
        self.statements: list[str] = []
        self.activity_writes = 0

    def execute(self, statement: str, params: list[Any] | None = None) -> Cursor:
        normalized = " ".join(statement.casefold().split())
        values = list(params or [])
        self.statements.append(normalized)
        if "pg_advisory_xact_lock" in normalized:
            return Cursor(one={"locked": True})
        if "from public.user_config_documents" in normalized and "for update" in normalized:
            return Cursor(
                all_rows=[
                    {"config_type": config_type, **self.documents[config_type]}
                    for config_type in CONFIG_TYPES
                ]
            )
        if "select revision from public.config_bundle_revisions" in normalized:
            return Cursor(one={"revision": 5})
        if "coalesce(max(revision), 0) + 1" in normalized:
            return Cursor(one={"next_revision": 6})
        if "insert into public.config_bundle_revisions" in normalized:
            return Cursor(
                one={
                    "bundle_revision_uuid": values[0],
                    "user_uuid": values[1],
                    "revision": values[2],
                    "preferences": {},
                    "generated_preview": {},
                    "validation_warnings": [],
                    "compiled_overrides": {},
                    "compiled_configs": {},
                    "config_revision_map": values[8].obj,
                    "config_hash": values[9],
                    "generator_version": values[10],
                    "source_ui_version": values[11],
                    "status": values[12],
                    "created_by_user_uuid": values[13],
                    "restored_from_bundle_revision_uuid": values[14],
                    "created_at": None,
                }
            )
        if "select set_config" in normalized:
            return Cursor(one={"set_config": values[-1]})
        if "update public.user_config_documents" in normalized:
            config_type = str(values[-1])
            if config_type == self.fail_config_type:
                raise RuntimeError("forced component failure")
            bundle_uuid = str(values[2])
            self.documents[config_type] = {
                "revision": 3,
                "bundle_revision_uuid": bundle_uuid,
            }
            self.version_rows.append({"config_type": config_type, "revision": 3})
            return Cursor(one=dict(self.documents[config_type]))
        if "from public.user_config_versions" in normalized:
            return Cursor(all_rows=list(self.version_rows))
        if "insert into public.user_activity_events" in normalized:
            self.activity_writes += 1
            return Cursor()
        raise AssertionError(f"Unexpected SQL: {normalized}")


class BundleStore:
    def __init__(self, connection: BundleConnection) -> None:
        self.connection = connection
        self.rolled_back = False

    @contextmanager
    def transaction(self) -> Iterator[BundleConnection]:
        try:
            yield self.connection
        except Exception:
            self.rolled_back = True
            raise


def _save(repository: PreferencesRepository, *, expected_revision: int = 5) -> dict[str, Any]:
    return repository.save_bundle(
        USER_UUID,
        compiled_overrides={config_type: {} for config_type in CONFIG_TYPES},
        preferences_json={"search_preferences": {"job_titles": ["Registered Nurse"]}},
        generated_preview={"search_titles": ["Registered Nurse", "RN"]},
        validation_warnings=[],
        generator_version="test-v1",
        source_ui_version="test-ui-v1",
        expected_revision=expected_revision,
        changed_by_user_uuid=ACTOR_UUID,
    )


def test_atomic_bundle_save_associates_exactly_three_versions_and_one_activity() -> None:
    connection = BundleConnection()
    repository = PreferencesRepository(store=BundleStore(connection))

    saved = _save(repository)

    assert saved["revision"] == 6
    assert saved["config_revision_map"] == {
        config_type: 3 for config_type in CONFIG_TYPES
    }
    assert saved["config_snapshot"]["schema_version"] == 2
    assert (
        saved["config_snapshot"]["config_bundle_revision_uuid"]
        == str(saved["bundle_revision_uuid"])
    )
    assert {row["config_type"] for row in connection.version_rows} == set(CONFIG_TYPES)
    assert connection.activity_writes == 1
    assert not any(
        "insert into public.user_config_versions" in statement
        for statement in connection.statements
    )


def test_bundle_save_rolls_back_when_any_component_write_fails() -> None:
    connection = BundleConnection(fail_config_type="jobs_config")
    store = BundleStore(connection)
    repository = PreferencesRepository(store=store)

    with pytest.raises(RuntimeError, match="forced component failure"):
        _save(repository)

    assert store.rolled_back is True
    assert connection.activity_writes == 0


def test_bundle_save_rejects_stale_expected_revision_before_writes() -> None:
    connection = BundleConnection()
    repository = PreferencesRepository(store=BundleStore(connection))

    with pytest.raises(ConfigBundleConflictError):
        _save(repository, expected_revision=4)

    assert not any(
        "insert into public.config_bundle_revisions" in statement
        for statement in connection.statements
    )


def test_coherent_bundle_requires_all_three_documents_to_share_identity() -> None:
    coherent = {
        config_type: {"bundle_revision_uuid": OLD_BUNDLE_UUID}
        for config_type in CONFIG_TYPES
    }
    mixed = {key: dict(value) for key, value in coherent.items()}
    mixed["jobs_config"]["bundle_revision_uuid"] = None

    assert _coherent_bundle_uuid(coherent) == OLD_BUNDLE_UUID
    assert _coherent_bundle_uuid(mixed) is None


class PipelineConnection:
    def __init__(self, *, completed_count: int = 0) -> None:
        self.insert_params: list[Any] | None = None
        self.completed_count = completed_count
        self.quota_statement = ""

    def execute(self, statement: str, params: list[Any] | None = None) -> Cursor:
        normalized = " ".join(statement.casefold().split())
        if "select count(*)" in normalized and "as count" in normalized:
            self.quota_statement = normalized
            return Cursor(one={"count": self.completed_count})
        if "insert into public.user_pipeline_runs" in normalized:
            self.insert_params = list(params or [])
            return Cursor(
                one={
                    "run_uuid": "55555555-5555-4555-8555-555555555555",
                    "user_uuid": USER_UUID,
                    "status": "queued",
                    "config_hash": self.insert_params[3],
                    "config_revision_map": {},
                    "submitted_at": None,
                    "started_at": None,
                    "completed_at": None,
                    "published_at": None,
                    "jobs_considered": 0,
                    "jobs_matched": 0,
                    "error_code": None,
                    "public_error_message": None,
                    "is_current_result": False,
                    "source_connector_run_uuid": None,
                    "is_bootstrap_run": False,
                    "trigger_type": "user_manual",
                    "bootstrap_uuid": None,
                    "config_bundle_revision_uuid": self.insert_params[-1],
                }
            )
        if "insert into public.user_pipeline_run_events" in normalized:
            return Cursor()
        raise AssertionError(f"Unexpected SQL: {normalized}")


class PipelineStore:
    def __init__(self, connection: PipelineConnection) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self) -> Iterator[PipelineConnection]:
        yield self.connection


def test_pipeline_run_persists_bundle_identity_from_immutable_snapshot() -> None:
    connection = PipelineConnection()
    snapshot = build_config_snapshot(
        {},
        config_bundle_revision_uuid=OLD_BUNDLE_UUID,
    )

    created = PipelineRunRepository(store=PipelineStore(connection)).create(
        user_uuid=USER_UUID,
        snapshot=snapshot,
        daily_limit=None,
    )

    assert connection.insert_params is not None
    assert connection.insert_params[-1] == OLD_BUNDLE_UUID
    assert created["config_bundle_revision_uuid"] == OLD_BUNDLE_UUID


def test_only_completed_pipeline_runs_consume_daily_quota() -> None:
    snapshot = build_config_snapshot({})
    allowed = PipelineConnection(completed_count=1)

    PipelineRunRepository(store=PipelineStore(allowed)).create(
        user_uuid=USER_UUID,
        snapshot=snapshot,
        daily_limit=2,
    )

    assert "status = 'completed'" in allowed.quota_statement
    assert "status <> 'cancelled'" not in allowed.quota_statement

    exhausted = PipelineConnection(completed_count=2)
    with pytest.raises(PipelineDailyLimitError):
        PipelineRunRepository(store=PipelineStore(exhausted)).create(
            user_uuid=USER_UUID,
            snapshot=snapshot,
            daily_limit=2,
        )


class QuotaStore:
    def __init__(self, *, count: int = 1) -> None:
        self.params: list[Any] = []
        self.count = count

    def fetch_one(self, statement: str, params: list[Any]) -> dict[str, Any]:
        normalized = " ".join(statement.casefold().split())
        self.params = params
        assert params[0] == USER_UUID
        assert params[2] == USER_UUID
        assert "status = 'completed'" in normalized
        assert "pipeline_quota_reset_at" in normalized
        return {"count": self.count}


def test_pipeline_quota_reports_successful_usage_and_reset_time() -> None:
    store = QuotaStore()
    quota = PipelineRunRepository(store=store).quota_for_user(
        USER_UUID,
        daily_limit=2,
    )

    assert quota["limit"] == 2
    assert quota["used"] == 1
    assert quota["remaining"] == 1
    assert quota["window_start"] == store.params[1]
    assert quota["window_end"] == store.params[4]
    assert quota["resets_at"] == store.params[4]


def test_pipeline_quota_window_resets_at_six_am_new_york() -> None:
    before_start, before_end = pipeline_quota_window(
        datetime(2026, 7, 12, 9, 59, tzinfo=timezone.utc)
    )
    after_start, after_end = pipeline_quota_window(
        datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
    )

    assert before_start == datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc)
    assert before_end == datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
    assert after_start == datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
    assert after_end == datetime(2026, 7, 13, 10, 0, tzinfo=timezone.utc)


def test_pipeline_quota_caps_legacy_overage_at_the_configured_limit() -> None:
    quota = PipelineRunRepository(store=QuotaStore(count=6)).quota_for_user(
        USER_UUID,
        daily_limit=2,
    )

    assert quota["used"] == 2
    assert quota["remaining"] == 0


class AliasCursor:
    def __init__(self, rows: list[list[Any]]) -> None:
        self.rows = rows

    def __enter__(self) -> "AliasCursor":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def executemany(self, statement: str, rows: list[list[Any]]) -> None:
        assert "insert into public.skill_alias_catalog" in " ".join(
            statement.casefold().split()
        )
        self.rows.extend(rows)


class AliasConnection:
    def __init__(self) -> None:
        self.rows: list[list[Any]] = []

    def cursor(self) -> AliasCursor:
        return AliasCursor(self.rows)


class AliasStore:
    def __init__(self, connection: AliasConnection) -> None:
        self.connection = connection

    @contextmanager
    def transaction(self) -> Iterator[AliasConnection]:
        yield self.connection


def test_alias_catalog_upsert_expands_compiler_alias_lists() -> None:
    connection = AliasConnection()
    repository = PreferencesRepository(store=AliasStore(connection))

    repository.upsert_skill_aliases(
        [
            {
                "canonical_skill": "Power BI",
                "aliases": ["Power BI", "PBI"],
                "category": "Business Intelligence",
                "source": "deterministic",
                "confidence": 1.0,
                "generator_version": "test-v1",
            }
        ]
    )

    assert [(row[0], row[2]) for row in connection.rows] == [
        ("Power BI", "Power BI"),
        ("Power BI", "PBI"),
    ]
