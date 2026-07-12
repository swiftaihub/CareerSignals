-- Sparse per-user overrides and immutable configuration history.

create table public.user_config_documents (
    config_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    config_type public.config_type not null,
    override_json jsonb not null default '{}'::jsonb,
    schema_version integer not null default 1,
    revision integer not null default 1,
    effective_config_hash text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_uuid, config_type)
);

create table public.user_config_versions (
    version_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    config_type public.config_type not null,
    revision integer not null,
    override_json jsonb not null,
    changed_by_user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    change_source text not null,
    created_at timestamptz not null default now(),
    unique (user_uuid, config_type, revision)
);

comment on table public.user_config_documents is
    'Current sparse JSON overrides; repository YAML remains the version-controlled default.';
comment on table public.user_config_versions is
    'Append-only configuration history. Restoring a revision creates a new row.';
