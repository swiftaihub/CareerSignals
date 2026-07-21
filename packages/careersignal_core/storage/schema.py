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
    create table if not exists raw.greenhouse_job_state (
        board_key varchar,
        job_post_id varchar,
        upstream_updated_at varchar,
        first_published_at varchar,
        detail_payload json,
        cached_at timestamp,
        primary key (board_key, job_post_id)
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
        location_normalized varchar,
        location_group varchar,
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
        visa_status varchar,
        visa_evidence varchar,
        visa_confidence varchar,
        match_score double,
        match_tier varchar,
        reasoning_summary varchar,
        inserted_at timestamp
    )
    """,
    """
    create table if not exists staging.shared_jobs_processed (
        job_id varchar,
        connector_run_uuid varchar,
        source varchar,
        source_job_id varchar,
        category_name varchar,
        job_title varchar,
        normalized_title varchar,
        company varchar,
        normalized_company varchar,
        industry varchar,
        location varchar,
        location_normalized varchar,
        location_group varchar,
        work_arrangement varchar,
        employment_type varchar,
        seniority varchar,
        salary_min double,
        salary_max double,
        salary_midpoint double,
        salary_range_text varchar,
        date_posted varchar,
        posted_at timestamp,
        date_collected varchar,
        jd_post_link varchar,
        apply_link varchar,
        job_description varchar,
        normalized_description varchar,
        visa_signal varchar,
        visa_status varchar,
        visa_evidence varchar,
        visa_confidence varchar,
        first_seen_at timestamp,
        last_seen_at timestamp,
        inserted_at timestamp,
        primary key (job_id, connector_run_uuid)
    )
    """,
    """
    create table if not exists staging.shared_job_observations (
        observation_id varchar primary key,
        connector_run_uuid varchar,
        job_id varchar,
        source varchar,
        source_job_id varchar,
        observed_at timestamp,
        source_url varchar
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
        user_uuid varchar,
        job_id varchar,
        application_status varchar,
        notes varchar,
        updated_at timestamp,
        primary key (user_id, job_id)
    )
    """,
    """
    create table if not exists app.user_config_snapshots (
        user_uuid varchar,
        run_uuid varchar,
        config_hash varchar,
        snapshot_version integer,
        config_revision_map json,
        config_snapshot json,
        staged_at timestamp,
        primary key (user_uuid, run_uuid)
    )
    """,
    """
    create table if not exists app.user_candidate_skills (
        user_uuid varchar,
        run_uuid varchar,
        config_hash varchar,
        skill varchar,
        skill_group varchar,
        in_candidate_profile boolean,
        staged_at timestamp,
        primary key (user_uuid, run_uuid, skill)
    )
    """,
    """
    create table if not exists app.user_job_preferences (
        user_uuid varchar,
        run_uuid varchar,
        config_hash varchar,
        category_name varchar,
        search_titles json,
        industries json,
        seniority json,
        target_titles json,
        target_industries json,
        locations json,
        work_arrangements json,
        employment_types json,
        visa_preferences json,
        excluded_companies json,
        excluded_titles json,
        min_base_salary double,
        preferred_base_salary double,
        title_match_weight double,
        required_skill_match_weight double,
        industry_match_weight double,
        salary_match_weight double,
        work_arrangement_match_weight double,
        visa_signal_match_weight double,
        top_match_threshold double,
        staged_at timestamp,
        primary key (user_uuid, run_uuid, category_name)
    )
    """,
    """
    create table if not exists app.user_skill_aliases (
        user_uuid varchar,
        run_uuid varchar,
        config_hash varchar,
        canonical_skill varchar,
        alias varchar,
        staged_at timestamp,
        primary key (user_uuid, run_uuid, canonical_skill, alias)
    )
    """,
]

MIGRATION_SQL = [
    "alter table staging.python_jobs_processed add column if not exists location_normalized varchar",
    "alter table staging.python_jobs_processed add column if not exists location_group varchar",
    "alter table staging.python_jobs_processed add column if not exists visa_status varchar",
    "alter table staging.python_jobs_processed add column if not exists visa_evidence varchar",
    "alter table staging.python_jobs_processed add column if not exists visa_confidence varchar",
    "alter table app.job_application_status add column if not exists user_uuid varchar",
    "alter table if exists intermediate.int_user_jobs_scored add column if not exists missing_candidate_skills varchar",
]


def init_motherduck_schema(service: MotherDuckService | None = None) -> None:
    """Create required MotherDuck schemas and raw/app/bridge tables."""

    md = service or MotherDuckService()
    with md.connect() as conn:
        for sql in SCHEMA_SQL:
            conn.execute(sql)
        for sql in TABLE_SQL:
            conn.execute(sql)
        for sql in MIGRATION_SQL:
            conn.execute(sql)
