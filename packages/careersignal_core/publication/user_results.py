"""Atomic, tenant-asserting publication of one user dbt run."""

from __future__ import annotations

import json
import math
from numbers import Real
from typing import Any, Iterable, Mapping
from uuid import UUID

from psycopg.types.json import Jsonb

from packages.careersignal_core.storage.postgres import PostgresStore


class UserResultPublicationError(RuntimeError):
    pass


RESULT_TABLES: tuple[str, ...] = (
    "mart_jobs_scored",
    "mart_top_matches",
    "mart_category_summary",
    "mart_skill_gap_analysis",
    "mart_company_priority_list",
)


def _normalize_result_value(value: Any) -> Any:
    """Convert dataframe non-finite numbers back to database NULLs."""

    if isinstance(value, Mapping):
        return {key: _normalize_result_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_result_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_normalize_result_value(item) for item in value)
    if isinstance(value, Real) and not math.isfinite(float(value)):
        return None
    return value


def _uuid(value: UUID | str, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as exc:
        raise UserResultPublicationError(f"{field} must be a valid UUID") from exc


def _validated_rows(
    rows: Iterable[Mapping[str, Any]], *, user_uuid: str, run_uuid: str
) -> list[dict[str, Any]]:
    materialized = [
        {key: _normalize_result_value(value) for key, value in dict(row).items()}
        for row in rows
    ]
    for row in materialized:
        try:
            row_user_uuid = str(UUID(str(row.get("user_uuid"))))
        except (TypeError, ValueError, AttributeError) as exc:
            raise UserResultPublicationError("User dbt output has an invalid user UUID") from exc
        try:
            row_run_uuid = str(UUID(str(row.get("run_uuid"))))
        except (TypeError, ValueError, AttributeError) as exc:
            raise UserResultPublicationError("User dbt output has an invalid run UUID") from exc
        if row_user_uuid != user_uuid:
            raise UserResultPublicationError("User dbt output contains a foreign user UUID")
        if row_run_uuid != run_uuid:
            raise UserResultPublicationError("User dbt output contains a foreign run UUID")
        row["user_uuid"] = row_user_uuid
        row["run_uuid"] = row_run_uuid
    return materialized


def _json_list(value: Any, *, scalar_as_item: bool = False) -> list[Any]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return [value] if scalar_as_item else []
        return parsed if isinstance(parsed, list) else ([parsed] if scalar_as_item else [])
    return [value] if scalar_as_item else []


def _require_unique_natural_key(
    rows: Iterable[Mapping[str, Any]], key: str, label: str
) -> None:
    values = [str(row.get(key) or "").strip() for row in rows]
    if any(not value for value in values):
        raise UserResultPublicationError(f"{label} output is missing {key}")
    if len(values) != len(set(values)):
        raise UserResultPublicationError(f"{label} output contains duplicate {key} values")


class UserResultsPublisher:
    def __init__(self, store: PostgresStore | None = None) -> None:
        self.store = store or PostgresStore()

    def publish_user_results(
        self,
        *,
        user_uuid: UUID | str,
        run_uuid: UUID | str,
        config_hash: str,
        results: Mapping[str, list[Mapping[str, Any]]],
    ) -> dict[str, int]:
        """Adapter for the worker pipeline's named dbt result frames."""

        user_key, run_key = _uuid(user_uuid, "user_uuid"), _uuid(run_uuid, "run_uuid")
        missing_tables = set(RESULT_TABLES) - set(results)
        if missing_tables:
            raise UserResultPublicationError(
                f"User dbt output is missing required result tables: {sorted(missing_tables)}"
            )
        validated_results = {
            table: _validated_rows(results[table], user_uuid=user_key, run_uuid=run_key)
            for table in RESULT_TABLES
        }
        for table, rows in validated_results.items():
            for row in rows:
                row_hash = row.get("config_hash")
                if row_hash is not None and str(row_hash) != config_hash:
                    raise UserResultPublicationError(
                        f"{table} output does not match the claimed configuration snapshot"
                    )

        matches = [dict(row) for row in validated_results["mart_jobs_scored"]]
        for row in matches:
            threshold = float(row.get("top_match_threshold") or 80)
            row.setdefault("is_top_match", float(row.get("match_score") or 0) >= threshold)
            row["required_skill_score"] = row.get(
                "required_skill_score", row.get("skill_score")
            )
            row["matched_skills"] = _json_list(
                row.get("matched_skills", row.get("required_skills"))
            )
            row["missing_skills"] = _json_list(row.get("missing_skills"))
            row["ranking_reasons"] = _json_list(
                row.get("ranking_reasons", row.get("reasoning_summary")),
                scalar_as_item=True,
            )

        def summaries(table: str, source_key: str, target_key: str) -> list[dict[str, Any]]:
            output: list[dict[str, Any]] = []
            for original in validated_results[table]:
                row = dict(original)
                natural_value = row.get(target_key, row.get(source_key))
                metrics = {
                    key: value
                    for key, value in row.items()
                    if key not in {"user_uuid", "run_uuid", source_key, target_key}
                }
                output.append(
                    {
                        "user_uuid": row["user_uuid"],
                        "run_uuid": row["run_uuid"],
                        target_key: natural_value,
                        "metrics": metrics,
                    }
                )
            return output

        return self.publish(
            user_uuid=user_key,
            run_uuid=run_key,
            config_hash=config_hash,
            matches=matches,
            category_summary=summaries("mart_category_summary", "category_name", "category_name"),
            skill_gap=summaries("mart_skill_gap_analysis", "skill", "canonical_skill"),
            company_priority=summaries(
                "mart_company_priority_list", "company", "company_name"
            ),
            jobs_considered=len(matches),
        )

    def publish(
        self,
        *,
        user_uuid: UUID | str,
        run_uuid: UUID | str,
        matches: Iterable[Mapping[str, Any]],
        category_summary: Iterable[Mapping[str, Any]],
        skill_gap: Iterable[Mapping[str, Any]],
        company_priority: Iterable[Mapping[str, Any]],
        jobs_considered: int,
        config_hash: str | None = None,
    ) -> dict[str, int]:
        user_key, run_key = _uuid(user_uuid, "user_uuid"), _uuid(run_uuid, "run_uuid")
        match_rows = _validated_rows(matches, user_uuid=user_key, run_uuid=run_key)
        category_rows = _validated_rows(category_summary, user_uuid=user_key, run_uuid=run_key)
        skill_rows = _validated_rows(skill_gap, user_uuid=user_key, run_uuid=run_key)
        company_rows = _validated_rows(company_priority, user_uuid=user_key, run_uuid=run_key)

        _require_unique_natural_key(match_rows, "job_id", "User match")
        _require_unique_natural_key(category_rows, "category_name", "Category summary")
        _require_unique_natural_key(skill_rows, "canonical_skill", "Skill gap")
        _require_unique_natural_key(company_rows, "company_name", "Company priority")

        with self.store.transaction() as connection:
            run = connection.execute(
                """
                select status::text as status, user_uuid, config_hash
                from public.user_pipeline_runs
                where run_uuid = %s
                for update
                """,
                [run_key],
            ).fetchone()
            if run is None or str(run["user_uuid"]) != user_key:
                raise UserResultPublicationError("Pipeline run does not belong to the requested user")
            if run["status"] != "running":
                raise UserResultPublicationError("Only a running pipeline may publish results")
            if config_hash is not None and str(run.get("config_hash") or "") != config_hash:
                raise UserResultPublicationError(
                    "Pipeline run configuration hash does not match the dbt output"
                )

            # A worker retry may only clear this exact unpublished partition.
            for table in (
                "user_job_matches",
                "user_category_summary",
                "user_skill_gap",
                "user_company_priority",
            ):
                connection.execute(
                    f"delete from public.{table} where user_uuid = %s and run_uuid = %s and is_current = false",
                    [user_key, run_key],
                )

            for row in match_rows:
                connection.execute(
                    """
                    insert into public.user_job_matches (
                      user_uuid, job_id, run_uuid, category_name, match_score,
                      title_score, required_skill_score, preferred_skill_score,
                      industry_score, salary_score, work_arrangement_score, visa_score,
                      matched_skills, missing_skills, ranking_reasons, is_top_match, is_current
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, false
                    )
                    """,
                    [
                        user_key,
                        row["job_id"],
                        run_key,
                        row.get("category_name"),
                        row.get("match_score", 0),
                        row.get("title_score"),
                        row.get("required_skill_score"),
                        row.get("preferred_skill_score"),
                        row.get("industry_score"),
                        row.get("salary_score"),
                        row.get("work_arrangement_score"),
                        row.get("visa_score"),
                        Jsonb(row.get("matched_skills") or []),
                        Jsonb(row.get("missing_skills") or []),
                        Jsonb(row.get("ranking_reasons") or []),
                        bool(row.get("is_top_match")),
                    ],
                )

            summary_specs = (
                ("user_category_summary", "category_name", category_rows),
                ("user_skill_gap", "canonical_skill", skill_rows),
                ("user_company_priority", "company_name", company_rows),
            )
            for table, natural_key, rows in summary_specs:
                for row in rows:
                    connection.execute(
                        f"""
                        insert into public.{table} (
                            user_uuid, run_uuid, {natural_key}, metrics, is_current
                        ) values (%s, %s, %s, %s, false)
                        """,
                        [user_key, run_key, row[natural_key], Jsonb(row.get("metrics") or row)],
                    )

            # The current-version switch and run/profile completion are one transaction.
            result_tables = (
                "user_job_matches",
                "user_category_summary",
                "user_skill_gap",
                "user_company_priority",
            )
            for table in result_tables:
                connection.execute(
                    f"update public.{table} set is_current = false where user_uuid = %s and is_current = true",
                    [user_key],
                )
            connection.execute(
                """
                update public.user_pipeline_runs
                set is_current_result = false
                where user_uuid = %s and is_current_result = true
                """,
                [user_key],
            )
            connection.execute(
                """
                update public.user_pipeline_runs
                set status = 'completed', completed_at = now(), published_at = now(),
                    jobs_considered = %s, jobs_matched = %s, is_current_result = true,
                    error_code = null, public_error_message = null, internal_error_message = null
                where run_uuid = %s
                """,
                [jobs_considered, len(match_rows), run_key],
            )
            for table in result_tables:
                connection.execute(
                    f"update public.{table} set is_current = true where user_uuid = %s and run_uuid = %s",
                    [user_key, run_key],
                )
            connection.execute(
                """
                update public.user_profiles
                set last_successful_pipeline_run_uuid = %s, last_activity_at = now()
                where user_uuid = %s
                """,
                [run_key, user_key],
            )
            connection.execute(
                """
                insert into public.user_pipeline_run_events (
                  run_uuid, user_uuid, event_level, event_type, message
                ) values (%s, %s, 'info', 'published', 'Pipeline results published atomically')
                """,
                [run_key, user_key],
            )

        return {
            "jobs_considered": jobs_considered,
            "jobs_matched": len(match_rows),
            "category_rows": len(category_rows),
            "skill_gap_rows": len(skill_rows),
            "company_rows": len(company_rows),
        }
