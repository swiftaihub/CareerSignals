-- Product activity and immutable administrative audit evidence.

create table public.user_activity_events (
    event_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    event_name text not null,
    event_time timestamptz not null default now(),
    session_id text,
    metadata jsonb not null default '{}'::jsonb
);

create table public.admin_audit_logs (
    audit_uuid uuid primary key default gen_random_uuid(),
    admin_user_uuid uuid not null references public.user_profiles(user_uuid) on delete restrict,
    target_user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    action_name text not null,
    before_state jsonb,
    after_state jsonb,
    request_id text,
    ip_address inet,
    user_agent text,
    created_at timestamptz not null default now()
);

comment on table public.user_activity_events is
    'Product-usage events used for DAU/WAU/MAU and operational analytics.';
comment on table public.admin_audit_logs is
    'Append-only audit log for every administrative mutation.';
