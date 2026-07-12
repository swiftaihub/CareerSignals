-- Entitlement history and provider-neutral billing event placeholders.

create table public.entitlement_events (
    entitlement_event_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    event_type text not null,
    days_delta integer not null default 0,
    amount_cents integer not null default 0,
    previous_expires_at timestamptz,
    new_expires_at timestamptz,
    performed_by_user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    external_reference text,
    note text,
    created_at timestamptz not null default now()
);

create table public.billing_events (
    billing_event_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete restrict,
    provider text not null default 'manual',
    event_type text not null,
    amount_cents integer not null default 0,
    currency text not null default 'usd',
    status text not null,
    external_event_id text unique,
    occurred_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

comment on table public.entitlement_events is
    'Append-only changes to expires_at; remaining days are always calculated, never stored.';
comment on table public.billing_events is
    'Future-compatible billing ledger. Administrative free-day grants are not revenue events.';
