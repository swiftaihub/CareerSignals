"""Idempotently seed the fixed read-only 20-job Demo partition.

This script creates no Supabase Auth identity and sends no external requests.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from packages.careersignal_core.settings import get_settings, project_root
from packages.careersignal_core.storage.postgres import PostgresStore


def _category(title: str) -> str:
    lowered = title.casefold()
    if "health" in lowered or "clinical" in lowered or "patient" in lowered:
        return "Healthcare Analytics"
    if "risk" in lowered or "fraud" in lowered or "lending" in lowered:
        return "Risk & Fintech"
    if "scientist" in lowered:
        return "Data Science"
    if "analytics engineer" in lowered or "bi engineer" in lowered:
        return "Analytics Engineering"
    return "Business Intelligence"


def _load_jobs(path: Path) -> list[dict[str, Any]]:
    jobs = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(jobs, list) or len(jobs) != 20:
        raise RuntimeError("Demo dataset must contain exactly 20 jobs")
    ids = {str(job.get("job_id")) for job in jobs}
    if len(ids) != 20 or any(not job_id.startswith("demo-") for job_id in ids):
        raise RuntimeError("Demo job IDs must be unique and stable")
    return jobs


def seed_demo(*, demo_user_uuid: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    configured_uuid = demo_user_uuid or settings.demo_user_uuid
    if not configured_uuid:
        raise RuntimeError("DEMO_USER_UUID is required")
    user_uuid = str(UUID(configured_uuid))
    run_uuid = str(uuid5(UUID(user_uuid), "careersignals-fixed-demo-results-v1"))
    jobs = _load_jobs(project_root() / "data" / "demo" / "demo_jobs.json")
    now = datetime.now(timezone.utc)
    store = PostgresStore()

    with store.transaction() as connection:
        connection.execute(
            """
            insert into public.user_profiles (
              user_uuid, auth_user_id, username, email, role, account_status,
              activated_at, expires_at
            ) values (%s, null, 'demo', null, 'demo', 'active', now(), null)
            on conflict (user_uuid) do update set
              auth_user_id = null, username = 'demo', email = null,
              role = 'demo', account_status = 'active', expires_at = null, deleted_at = null
            """,
            [user_uuid],
        )
        connection.execute(
            """
            insert into public.user_config_documents (user_uuid, config_type)
            select %s, config_type from unnest(enum_range(null::public.config_type)) config_type
            on conflict (user_uuid, config_type) do update set override_json = '{}'::jsonb
            """,
            [user_uuid],
        )
        connection.execute(
            "update public.user_profiles set last_successful_pipeline_run_uuid = null where user_uuid = %s",
            [user_uuid],
        )
        connection.execute("delete from public.user_pipeline_runs where user_uuid = %s", [user_uuid])
        connection.execute(
            """
            insert into public.user_pipeline_runs (
              run_uuid, user_uuid, status, config_snapshot, config_hash, config_revision_map,
              submitted_at, started_at, completed_at, published_at,
              jobs_considered, jobs_matched, is_current_result, worker_id
            ) values (
              %s, %s, 'completed', %s, %s, %s, now(), now(), now(), now(), 20, 20, true, 'demo-seed'
            )
            """,
            [
                run_uuid,
                user_uuid,
                Jsonb({"schema_version": 1, "demo": True, "fixed": True}),
                hashlib.sha256(b"careersignals-fixed-demo-v1").hexdigest(),
                Jsonb({"candidate_profile": 1, "jobs_config": 1, "skill_taxonomy": 1}),
            ],
        )
        for job in jobs:
            description = str(job["job_description"])
            connection.execute(
                """
                insert into public.job_postings (
                  job_id, source_name, source_job_id, title, company_name, location,
                  location_group, industry, seniority, work_arrangement, visa_signal,
                  salary_min, salary_max, salary_currency, posted_at, apply_url,
                  job_description, job_description_hash, first_seen_at, last_seen_at,
                  is_active, updated_at
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, true, now()
                )
                on conflict (job_id) do update set
                  title = excluded.title, company_name = excluded.company_name,
                  location = excluded.location, location_group = excluded.location_group,
                  industry = excluded.industry, seniority = excluded.seniority,
                  work_arrangement = excluded.work_arrangement, visa_signal = excluded.visa_signal,
                  salary_min = excluded.salary_min, salary_max = excluded.salary_max,
                  posted_at = excluded.posted_at, apply_url = excluded.apply_url,
                  job_description = excluded.job_description,
                  job_description_hash = excluded.job_description_hash,
                  last_seen_at = excluded.last_seen_at, is_active = true, updated_at = now()
                """,
                [
                    job["job_id"], job["source_name"], job["source_job_id"], job["title"],
                    job["company_name"], job["location"], job["location_group"], job["industry"],
                    job["seniority"], job["work_arrangement"], job["visa_signal"],
                    job["salary_min"], job["salary_max"], job["salary_currency"], job["posted_at"],
                    job["apply_url"], description, hashlib.sha256(description.encode()).hexdigest(),
                    job["posted_at"], now,
                ],
            )
            score = float(job["match_score"])
            connection.execute(
                """
                insert into public.user_job_matches (
                  user_uuid, job_id, run_uuid, category_name, match_score,
                  title_score, required_skill_score, preferred_skill_score, industry_score,
                  salary_score, work_arrangement_score, visa_score, matched_skills,
                  missing_skills, ranking_reasons, is_top_match, is_current
                ) values (
                  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, true
                )
                """,
                [
                    user_uuid, job["job_id"], run_uuid, _category(job["title"]), score,
                    min(100, score + 3), score, max(0, score - 8), score,
                    min(100, score + 2), score, 75,
                    Jsonb(["SQL", "Python"]), Jsonb([]),
                    Jsonb(["Curated fixed Demo match"]), score >= 80,
                ],
            )

        categories = Counter(_category(job["title"]) for job in jobs)
        for category, count in categories.items():
            connection.execute(
                """
                insert into public.user_category_summary (
                  user_uuid, run_uuid, category_name, metrics, is_current
                ) values (%s, %s, %s, %s, true)
                """,
                [user_uuid, run_uuid, category, Jsonb({"jobs_found": count})],
            )
        for skill, count in (("SQL", 15), ("Python", 10), ("dbt", 5), ("Power BI", 4)):
            connection.execute(
                """
                insert into public.user_skill_gap (
                  user_uuid, run_uuid, canonical_skill, metrics, is_current
                ) values (%s, %s, %s, %s, true)
                """,
                [user_uuid, run_uuid, skill, Jsonb({"appears_in_job_count": count, "gap_priority": "Low"})],
            )
        for job in jobs[:10]:
            connection.execute(
                """
                insert into public.user_company_priority (
                  user_uuid, run_uuid, company_name, metrics, is_current
                ) values (%s, %s, %s, %s, true)
                """,
                [
                    user_uuid,
                    run_uuid,
                    job["company_name"],
                    Jsonb({"highest_match_score": job["match_score"], "priority": "High"}),
                ],
            )
        connection.execute(
            """
            update public.user_profiles
            set last_successful_pipeline_run_uuid = %s, last_activity_at = now()
            where user_uuid = %s
            """,
            [run_uuid, user_uuid],
        )
    return {"user_uuid": user_uuid, "run_uuid": run_uuid, "jobs": 20}


def main() -> None:
    result = seed_demo()
    print(f"Seeded fixed Demo partition with {result['jobs']} jobs for {result['user_uuid']}.")


if __name__ == "__main__":
    main()
