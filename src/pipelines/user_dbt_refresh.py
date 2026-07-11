"""Worker entry point for a single user-scoped dbt refresh.

No Connector package is imported or instantiated by this module.
"""

from __future__ import annotations

from typing import Any

from packages.careersignal_core.dbt.runner import run_user_dbt_build
from packages.careersignal_core.storage.motherduck import MotherDuckService
from src.pipelines.user_config_staging import stage_user_config_snapshot

USER_RESULT_TABLES: tuple[str, ...] = (
    "mart.mart_jobs_scored",
    "mart.mart_top_matches",
    "mart.mart_category_summary",
    "mart.mart_skill_gap_analysis",
    "mart.mart_company_priority_list",
)


def _frame_records(frame: Any) -> list[dict[str, Any]]:
    if hasattr(frame, "where"):
        frame = frame.where(frame.notna(), None)
    return frame.to_dict(orient="records") if hasattr(frame, "to_dict") else []


def read_user_result_partition(
    service: MotherDuckService,
    user_uuid: str,
    run_uuid: str,
) -> dict[str, list[dict[str, Any]]]:
    """Read only the freshly tested user/run result partition."""

    results: dict[str, list[dict[str, Any]]] = {}
    for table in USER_RESULT_TABLES:
        name = table.split(".", 1)[1]
        frame = service.query_df(
            f"select * from {table} where user_uuid = ? and run_uuid = ?",
            [user_uuid, run_uuid],
        )
        results[name] = _frame_records(frame)
    return results


def _publish_user_results(
    publisher: Any,
    *,
    user_uuid: str,
    run_uuid: str,
    config_hash: str,
    results: dict[str, list[dict[str, Any]]],
) -> Any:
    kwargs = {
        "user_uuid": user_uuid,
        "run_uuid": run_uuid,
        "config_hash": config_hash,
        "results": results,
    }
    if hasattr(publisher, "publish_user_results"):
        return publisher.publish_user_results(**kwargs)
    if callable(publisher):
        return publisher(**kwargs)
    raise TypeError("publisher must be callable or expose publish_user_results")


def run_user_dbt_refresh(
    user_uuid: str,
    run_uuid: str,
    config_snapshot: dict[str, Any],
    *,
    publisher: Any | None = None,
) -> dict[str, Any]:
    """Stage, build/test, and optionally publish one immutable user partition."""

    service = MotherDuckService()
    staged = stage_user_config_snapshot(
        user_uuid,
        run_uuid,
        config_snapshot,
        service=service,
    )
    user = staged["user_uuid"]
    run = staged["run_uuid"]
    run_user_dbt_build(user, run)
    results = read_user_result_partition(service, user, run)
    publication_result = None
    if publisher is not None:
        publication_result = _publish_user_results(
            publisher,
            user_uuid=user,
            run_uuid=run,
            config_hash=staged["config_hash"],
            results=results,
        )
    return {
        "user_uuid": user,
        "run_uuid": run,
        "config_hash": staged["config_hash"],
        "staged_rows": staged["staged_rows"],
        "dbt_completed": True,
        "result_counts": {name: len(rows) for name, rows in results.items()},
        "published": publisher is not None,
        "publication_result": publication_result,
    }
