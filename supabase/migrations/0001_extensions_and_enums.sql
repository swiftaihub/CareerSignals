-- CareerSignals SaaS control-plane primitives.
-- This migration is intentionally data-free and contains no credentials.

create extension if not exists pgcrypto;
create extension if not exists citext;

create type public.user_role as enum (
    'user',
    'admin',
    'demo'
);

create type public.account_status as enum (
    'pending',
    'active',
    'expired',
    'suspended',
    'deleted'
);

create type public.pipeline_status as enum (
    'queued',
    'running',
    'completed',
    'failed',
    'cancelled'
);

create type public.connector_run_status as enum (
    'queued',
    'running',
    'completed',
    'partial',
    'failed',
    'cancelled'
);

create type public.config_type as enum (
    'candidate_profile',
    'jobs_config',
    'skill_taxonomy'
);

comment on type public.user_role is
    'Authorization role derived on the server; never trusted from browser input.';
comment on type public.account_status is
    'Lifecycle state for a CareerSignals tenant account.';
comment on type public.pipeline_status is
    'State machine values for a user-scoped dbt pipeline run.';
comment on type public.connector_run_status is
    'State machine values for platform-owned connector refreshes.';
comment on type public.config_type is
    'Repository-default configuration documents that support per-user overrides.';
