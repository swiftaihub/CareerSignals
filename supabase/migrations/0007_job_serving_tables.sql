-- PostgreSQL serving copy: shared canonical jobs plus versioned user result partitions.

create table public.job_postings (
    job_id text primary key,
    source_name text not null,
    source_job_id text,
    title text not null,
    company_name text,
    location text,
    location_group text,
    industry text,
    seniority text,
    work_arrangement text,
    visa_signal text,
    salary_min numeric,
    salary_max numeric,
    salary_currency text,
    posted_at timestamptz,
    apply_url text,
    job_description text,
    job_description_hash text,
    first_seen_at timestamptz not null,
    last_seen_at timestamptz not null,
    is_active boolean not null default true,
    shared_connector_run_uuid uuid references public.connector_refresh_runs(connector_run_uuid) on delete set null,
    updated_at timestamptz not null default now()
);

create table public.user_job_matches (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    job_id text not null references public.job_postings(job_id) on delete restrict,
    run_uuid uuid not null,
    category_name text,
    match_score numeric not null,
    title_score numeric,
    required_skill_score numeric,
    preferred_skill_score numeric,
    industry_score numeric,
    salary_score numeric,
    work_arrangement_score numeric,
    visa_score numeric,
    matched_skills jsonb not null default '[]'::jsonb,
    missing_skills jsonb not null default '[]'::jsonb,
    ranking_reasons jsonb not null default '[]'::jsonb,
    is_top_match boolean not null default false,
    is_current boolean not null default false,
    created_at timestamptz not null default now(),
    primary key (user_uuid, job_id, run_uuid),
    constraint user_job_matches_run_user_fk
        foreign key (run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete cascade
);

create table public.user_job_statuses (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    job_id text not null references public.job_postings(job_id) on delete restrict,
    application_status text not null default 'not_started',
    notes text,
    updated_at timestamptz not null default now(),
    primary key (user_uuid, job_id)
);

create table public.user_category_summary (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    run_uuid uuid not null,
    category_name text not null,
    metrics jsonb not null,
    is_current boolean not null default false,
    primary key (user_uuid, run_uuid, category_name),
    constraint user_category_summary_run_user_fk
        foreign key (run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete cascade
);

create table public.user_skill_gap (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    run_uuid uuid not null,
    canonical_skill text not null,
    metrics jsonb not null,
    is_current boolean not null default false,
    primary key (user_uuid, run_uuid, canonical_skill),
    constraint user_skill_gap_run_user_fk
        foreign key (run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete cascade
);

create table public.user_company_priority (
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    run_uuid uuid not null,
    company_name text not null,
    metrics jsonb not null,
    is_current boolean not null default false,
    primary key (user_uuid, run_uuid, company_name),
    constraint user_company_priority_run_user_fk
        foreign key (run_uuid, user_uuid)
        references public.user_pipeline_runs(run_uuid, user_uuid)
        on delete cascade
);

comment on table public.job_postings is
    'Shared canonical job universe. Ownership is expressed only through user_job_matches.';
comment on table public.user_job_matches is
    'Versioned user-specific match output; publication initially inserts is_current=false.';
comment on table public.user_job_statuses is
    'Mutable per-user workflow status, independent of pipeline result versions.';
comment on column public.user_job_statuses.application_status is
    'Canonical lowercase value; a trigger maps legacy title-cased/not-applied inputs.';
