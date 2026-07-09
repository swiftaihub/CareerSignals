"""MotherDuck schema initialization."""

from __future__ import annotations

from packages.careersignal_core.storage.motherduck import MotherDuckService

SCHEMA_SQL = [
    "create schema if not exists raw",
    "create schema if not exists staging",
    "create schema if not exists intermediate",
    "create schema if not exists mart",
    "create schema if not exists app",
]

TABLE_SQL = [
    """
    create table if not exists raw.ingestion_runs (
        run_id varchar primary key,
        run_started_at timestamp,
        run_completed_at timestamp,
        status varchar,
        data_mode varchar,
        total_raw_jobs integer,
        total_processed_jobs integer,
        total_deduplicated_jobs integer,
        total_top_matches integer,
        excel_output_path varchar,
        error_message varchar
    )
    """,
    """
    create table if not exists raw.job_posts_raw (
        raw_record_id varchar primary key,
        run_id varchar,
        source varchar,
        category_name varchar,
        query_title varchar,
        query_location varchar,
        raw_job_key varchar,
        raw_payload json,
        raw_payload_hash varchar,
        fetched_at timestamp,
        source_url varchar,
        connector_status varchar
    )
    """,
    """
    create table if not exists raw.connector_errors (
        error_id varchar primary key,
        run_id varchar,
        source varchar,
        category_name varchar,
        query_title varchar,
        error_message varchar,
        error_type varchar,
        occurred_at timestamp
    )
    """,
    """
    create table if not exists staging.python_jobs_processed (
        job_id varchar,
        run_id varchar,
        source varchar,
        category_name varchar,
        job_title varchar,
        normalized_title varchar,
        company varchar,
        industry varchar,
        location varchar,
        work_arrangement varchar,
        employment_type varchar,
        seniority varchar,
        salary_min double,
        salary_max double,
        salary_midpoint double,
        salary_range_text varchar,
        date_posted varchar,
        date_collected varchar,
        jd_post_link varchar,
        apply_link varchar,
        job_description varchar,
        required_skills varchar,
        preferred_skills varchar,
        all_extracted_skills varchar,
        visa_signal varchar,
        match_score double,
        match_tier varchar,
        reasoning_summary varchar,
        inserted_at timestamp
    )
    """,
    """
    create table if not exists staging.python_candidate_skills (
        skill varchar primary key,
        skill_group varchar,
        in_candidate_profile boolean
    )
    """,
    """
    create table if not exists app.job_application_status (
        user_id varchar,
        job_id varchar,
        application_status varchar,
        notes varchar,
        updated_at timestamp,
        primary key (user_id, job_id)
    )
    """,
]


def init_motherduck_schema(service: MotherDuckService | None = None) -> None:
    """Create required MotherDuck schemas and raw/app/bridge tables."""

    md = service or MotherDuckService()
    with md.connect() as conn:
        for sql in SCHEMA_SQL:
            conn.execute(sql)
        for sql in TABLE_SQL:
            conn.execute(sql)
