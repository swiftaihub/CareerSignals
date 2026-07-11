from __future__ import annotations

import ast
import importlib
from pathlib import Path
import sys

from src.config.loader import build_config_snapshot

USER_UUID = "11111111-1111-4111-8111-111111111111"
RUN_UUID = "22222222-2222-4222-8222-222222222222"


def test_user_pipeline_modules_have_no_connector_imports() -> None:
    for path in (
        Path("src/pipelines/user_dbt_refresh.py"),
        Path("src/pipelines/user_config_staging.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ] + [
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        ]
        assert not any(name.startswith("src.connectors") for name in imported)


def test_importing_user_pipeline_loads_zero_connector_modules() -> None:
    before = {name for name in sys.modules if name.startswith("src.connectors")}

    importlib.import_module("src.pipelines.user_dbt_refresh")

    after = {name for name in sys.modules if name.startswith("src.connectors")}
    assert after == before


def test_user_refresh_stages_and_builds_without_connector_calls(monkeypatch) -> None:
    module = importlib.import_module("src.pipelines.user_dbt_refresh")
    calls: list[str] = []

    class FakeService:
        pass

    monkeypatch.setattr(module, "MotherDuckService", FakeService)
    monkeypatch.setattr(
        module,
        "stage_user_config_snapshot",
        lambda user_uuid, run_uuid, snapshot, service: {
            "user_uuid": user_uuid,
            "run_uuid": run_uuid,
            "config_hash": snapshot["config_hash"],
            "staged_rows": {"candidate_skills": 1},
        },
    )
    monkeypatch.setattr(
        module,
        "run_user_dbt_build",
        lambda user_uuid, run_uuid: calls.append(f"dbt:{user_uuid}:{run_uuid}"),
    )
    monkeypatch.setattr(
        module,
        "read_user_result_partition",
        lambda service, user_uuid, run_uuid: {"mart_jobs_scored": []},
    )

    summary = module.run_user_dbt_refresh(
        USER_UUID,
        RUN_UUID,
        build_config_snapshot({}),
    )

    assert calls == [f"dbt:{USER_UUID}:{RUN_UUID}"]
    assert summary["dbt_completed"] is True
    assert summary["published"] is False
