-- Application tenant identities. Supabase auth.users remains the credential store.

create table public.user_profiles (
    user_uuid uuid primary key default gen_random_uuid(),
    auth_user_id uuid unique references auth.users(id) on delete cascade,
    username citext not null unique,
    email citext,
    role public.user_role not null default 'user',
    account_status public.account_status not null default 'pending',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    activated_at timestamptz,
    expires_at timestamptz,
    last_login_at timestamptz,
    last_activity_at timestamptz,
    last_successful_pipeline_run_uuid uuid,
    deleted_at timestamptz,
    constraint user_profiles_demo_auth_check check (
        (role = 'demo' and auth_user_id is null)
        or (role <> 'demo' and auth_user_id is not null)
    ),
    constraint user_profiles_nonexpiring_roles_check check (
        role not in ('admin', 'demo') or expires_at is null
    )
);

comment on table public.user_profiles is
    'Application tenant profiles mapped to Supabase Auth; passwords are never stored here.';
comment on column public.user_profiles.user_uuid is
    'Stable application tenant identifier used by every user-owned relation.';
comment on column public.user_profiles.auth_user_id is
    'Supabase Auth subject. Null only for the fixed read-only Demo profile.';
comment on column public.user_profiles.last_successful_pipeline_run_uuid is
    'Pointer to the last atomically published run; its same-user FK is added after run tables exist.';
