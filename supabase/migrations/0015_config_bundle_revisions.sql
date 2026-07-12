-- Coherent preference/configuration bundles and the shared skill-alias catalog.
--
-- Legacy pipeline snapshots remain valid without a bundle UUID. Existing
-- current documents are rolled into one migration-authored bundle per user;
-- older component versions and historical runs intentionally remain nullable.

create table public.config_bundle_revisions (
    bundle_revision_uuid uuid primary key default gen_random_uuid(),
    user_uuid uuid not null references public.user_profiles(user_uuid) on delete cascade,
    revision integer not null,
    preferences_json jsonb not null default '{}'::jsonb,
    generated_preview_json jsonb not null default '{}'::jsonb,
    validation_warnings jsonb not null default '[]'::jsonb,
    compiled_overrides jsonb not null,
    compiled_configs jsonb,
    config_revision_map jsonb not null,
    config_hash text,
    generator_version text not null,
    source_ui_version text not null,
    status text not null default 'saved',
    created_by_user_uuid uuid references public.user_profiles(user_uuid) on delete set null,
    restored_from_bundle_revision_uuid uuid,
    created_at timestamptz not null default now(),
    constraint config_bundle_revisions_user_revision_key unique (user_uuid, revision),
    constraint config_bundle_revisions_user_bundle_key unique (user_uuid, bundle_revision_uuid),
    constraint config_bundle_revisions_revision_check check (revision >= 1),
    constraint config_bundle_revisions_preferences_object_check
        check (jsonb_typeof(preferences_json) = 'object'),
    constraint config_bundle_revisions_preview_object_check
        check (jsonb_typeof(generated_preview_json) = 'object'),
    constraint config_bundle_revisions_warnings_array_check
        check (jsonb_typeof(validation_warnings) = 'array'),
    constraint config_bundle_revisions_overrides_object_check
        check (jsonb_typeof(compiled_overrides) = 'object'),
    constraint config_bundle_revisions_configs_object_check
        check (compiled_configs is null or jsonb_typeof(compiled_configs) = 'object'),
    constraint config_bundle_revisions_revision_map_object_check
        check (jsonb_typeof(config_revision_map) = 'object'),
    constraint config_bundle_revisions_payload_size_check check (
        pg_column_size(preferences_json)
        + pg_column_size(generated_preview_json)
        + pg_column_size(validation_warnings)
        + pg_column_size(compiled_overrides)
        + coalesce(pg_column_size(compiled_configs), 0)
        <= 2097152
    ),
    constraint config_bundle_revisions_generator_check check (btrim(generator_version) <> ''),
    constraint config_bundle_revisions_ui_version_check check (btrim(source_ui_version) <> ''),
    constraint config_bundle_revisions_status_check check (
        status in ('saved', 'restored', 'reset', 'legacy_import', 'default_seed')
    ),
    constraint config_bundle_revisions_restore_user_fk
        foreign key (user_uuid, restored_from_bundle_revision_uuid)
        references public.config_bundle_revisions(user_uuid, bundle_revision_uuid)
        deferrable initially deferred
);

create table public.skill_alias_catalog (
    skill_alias_uuid uuid primary key default gen_random_uuid(),
    canonical_skill text not null,
    normalized_canonical_skill text not null,
    alias text not null,
    normalized_alias text not null,
    category text,
    industry text,
    source text not null,
    confidence numeric(5, 4) not null default 1,
    generator_version text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint skill_alias_catalog_pair_key
        unique (normalized_canonical_skill, normalized_alias),
    constraint skill_alias_catalog_canonical_check check (btrim(canonical_skill) <> ''),
    constraint skill_alias_catalog_normalized_canonical_check
        check (btrim(normalized_canonical_skill) <> ''),
    constraint skill_alias_catalog_alias_check check (btrim(alias) <> ''),
    constraint skill_alias_catalog_normalized_alias_check check (btrim(normalized_alias) <> ''),
    constraint skill_alias_catalog_source_check check (btrim(source) <> ''),
    constraint skill_alias_catalog_generator_check check (btrim(generator_version) <> ''),
    constraint skill_alias_catalog_confidence_check check (confidence between 0 and 1)
);

alter table public.user_config_documents
    add column bundle_revision_uuid uuid;

alter table public.user_config_versions
    add column bundle_revision_uuid uuid;

alter table public.user_pipeline_runs
    add column config_bundle_revision_uuid uuid;

alter table public.user_config_documents
    add constraint user_config_documents_bundle_user_fk
    foreign key (user_uuid, bundle_revision_uuid)
    references public.config_bundle_revisions(user_uuid, bundle_revision_uuid)
    deferrable initially deferred;

alter table public.user_config_versions
    add constraint user_config_versions_bundle_user_fk
    foreign key (user_uuid, bundle_revision_uuid)
    references public.config_bundle_revisions(user_uuid, bundle_revision_uuid)
    deferrable initially deferred,
    add constraint user_config_versions_one_type_per_bundle
    unique (user_uuid, bundle_revision_uuid, config_type);

alter table public.user_pipeline_runs
    add constraint user_pipeline_runs_bundle_user_fk
    foreign key (user_uuid, config_bundle_revision_uuid)
    references public.config_bundle_revisions(user_uuid, bundle_revision_uuid)
    deferrable initially deferred;

-- A legacy/direct single-document mutation cannot remain associated with an
-- older three-document bundle. The atomic repository supplies a new bundle
-- UUID in the same update, while direct override-only writes are cleared.
create or replace function public.prepare_config_document_revision()
returns trigger
language plpgsql
set search_path = pg_catalog, public
as $function$
begin
    if tg_op = 'UPDATE' then
        if new.config_uuid <> old.config_uuid
            or new.user_uuid <> old.user_uuid
            or new.config_type <> old.config_type then
            raise exception 'Configuration document identity fields are immutable.'
                using errcode = '23514';
        end if;
        if new.override_json is distinct from old.override_json
            and new.bundle_revision_uuid is not distinct from old.bundle_revision_uuid then
            new.bundle_revision_uuid := null;
        end if;
        new.revision := old.revision + 1;
        new.created_at := old.created_at;
        if new.override_json is distinct from old.override_json
            and new.effective_config_hash is not distinct from old.effective_config_hash then
            new.effective_config_hash := null;
        end if;
    else
        new.revision := greatest(coalesce(new.revision, 1), 1);
    end if;
    return new;
end
$function$;

-- Bundle writes rely on the existing document trigger for exactly one version
-- per component. Bundle saves emit one bundle-level activity event rather than
-- three duplicate document events.
create or replace function public.record_config_document_version()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    acting_user_uuid uuid;
    source_name text;
begin
    acting_user_uuid := public.current_app_user_uuid();
    if acting_user_uuid is null then
        acting_user_uuid := nullif(
            current_setting('careersignals.changed_by_user_uuid', true),
            ''
        )::uuid;
        source_name := coalesce(
            nullif(current_setting('careersignals.config_change_source', true), ''),
            case when tg_op = 'INSERT' then 'service_insert' else 'service_update' end
        );
    else
        source_name := case
            when public.current_app_role() = 'admin' then 'admin_direct_update'
            when tg_op = 'INSERT' then 'user_direct_insert'
            else 'user_direct_update'
        end;
    end if;

    insert into public.user_config_versions (
        user_uuid,
        config_type,
        revision,
        override_json,
        changed_by_user_uuid,
        change_source,
        bundle_revision_uuid
    )
    values (
        new.user_uuid,
        new.config_type,
        new.revision,
        new.override_json,
        acting_user_uuid,
        source_name,
        new.bundle_revision_uuid
    )
    on conflict (user_uuid, config_type, revision) do nothing;

    if tg_op = 'UPDATE' and new.bundle_revision_uuid is null then
        insert into public.user_activity_events (
            user_uuid,
            event_name,
            metadata
        )
        values (
            new.user_uuid,
            'config_updated',
            jsonb_build_object(
                'config_type', new.config_type,
                'revision', new.revision,
                'change_source', source_name
            )
        );
    end if;

    return new;
end
$function$;

-- Give every existing current three-document set a coherent legacy bundle.
-- The document update intentionally creates a new same-content component
-- revision, preserving all earlier append-only versions unchanged.
insert into public.config_bundle_revisions (
    user_uuid,
    revision,
    preferences_json,
    generated_preview_json,
    validation_warnings,
    compiled_overrides,
    compiled_configs,
    config_revision_map,
    config_hash,
    generator_version,
    source_ui_version,
    status
)
select
    documents.user_uuid,
    1,
    '{}'::jsonb,
    '{}'::jsonb,
    jsonb_build_array(
        'Imported from legacy configuration documents; preferences will be reverse-mapped on first load.'
    ),
    jsonb_object_agg(documents.config_type::text, documents.override_json),
    null,
    jsonb_object_agg(documents.config_type::text, to_jsonb(documents.revision + 1)),
    null,
    'legacy-import-v1',
    'migration-0015',
    'legacy_import'
from public.user_config_documents as documents
group by documents.user_uuid
having count(*) = 3;

select set_config('careersignals.allow_demo_seed', 'on', true);
select set_config('careersignals.config_change_source', 'bundle_backfill', true);

update public.user_config_documents as documents
set bundle_revision_uuid = bundles.bundle_revision_uuid
from public.config_bundle_revisions as bundles
where bundles.user_uuid = documents.user_uuid
  and bundles.status = 'legacy_import'
  and bundles.revision = 1;

-- Flush deferred same-user FK checks before PostgreSQL builds indexes on the
-- referenced bundle table later in this migration.
set constraints all immediate;

select set_config('careersignals.allow_demo_seed', 'off', true);
select set_config('careersignals.config_change_source', '', true);

-- Auth-created users after this migration start with one coherent bundle of
-- empty overrides. Repository defaults remain version-controlled in YAML.
create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $function$
declare
    requested_username text;
    created_user_uuid uuid;
    initial_bundle_uuid uuid;
begin
    requested_username := nullif(
        btrim(coalesce(new.raw_user_meta_data ->> 'username', '')),
        ''
    );

    if requested_username is null then
        requested_username := 'user_' || left(replace(new.id::text, '-', ''), 12);
    end if;

    insert into public.user_profiles (
        auth_user_id,
        username,
        email,
        role,
        account_status
    )
    values (
        new.id,
        requested_username,
        new.email,
        'user',
        'pending'
    )
    on conflict (auth_user_id) do update
        set email = excluded.email
    returning user_uuid into created_user_uuid;

    if not exists (
        select 1
        from public.user_config_documents
        where user_uuid = created_user_uuid
    ) then
        insert into public.config_bundle_revisions (
            user_uuid,
            revision,
            preferences_json,
            generated_preview_json,
            validation_warnings,
            compiled_overrides,
            compiled_configs,
            config_revision_map,
            generator_version,
            source_ui_version,
            status
        )
        values (
            created_user_uuid,
            1,
            '{}'::jsonb,
            '{}'::jsonb,
            jsonb_build_array('Preferences are currently derived from repository defaults.'),
            jsonb_build_object(
                'candidate_profile', '{}'::jsonb,
                'jobs_config', '{}'::jsonb,
                'skill_taxonomy', '{}'::jsonb
            ),
            null,
            jsonb_build_object(
                'candidate_profile', 1,
                'jobs_config', 1,
                'skill_taxonomy', 1
            ),
            'repository-defaults-v1',
            'auth-signup',
            'default_seed'
        )
        returning bundle_revision_uuid into initial_bundle_uuid;

        insert into public.user_config_documents (
            user_uuid,
            config_type,
            bundle_revision_uuid
        )
        values
            (created_user_uuid, 'candidate_profile', initial_bundle_uuid),
            (created_user_uuid, 'jobs_config', initial_bundle_uuid),
            (created_user_uuid, 'skill_taxonomy', initial_bundle_uuid);
    else
        insert into public.user_config_documents (user_uuid, config_type)
        values
            (created_user_uuid, 'candidate_profile'),
            (created_user_uuid, 'jobs_config'),
            (created_user_uuid, 'skill_taxonomy')
        on conflict (user_uuid, config_type) do nothing;
    end if;

    return new;
end
$function$;

drop trigger if exists skill_alias_catalog_set_updated_at on public.skill_alias_catalog;
create trigger skill_alias_catalog_set_updated_at
before update on public.skill_alias_catalog
for each row execute function public.set_row_updated_at();

drop trigger if exists config_bundle_revisions_append_only on public.config_bundle_revisions;
create trigger config_bundle_revisions_append_only
before update or delete on public.config_bundle_revisions
for each row execute function public.reject_append_only_mutation();

drop trigger if exists config_bundle_revisions_reject_demo_mutation on public.config_bundle_revisions;
create trigger config_bundle_revisions_reject_demo_mutation
before insert or update or delete on public.config_bundle_revisions
for each row execute function public.reject_demo_mutation();

create index config_bundle_revisions_user_created_idx
on public.config_bundle_revisions(user_uuid, created_at desc);

create index user_config_documents_bundle_idx
on public.user_config_documents(user_uuid, bundle_revision_uuid);

create index user_config_versions_bundle_idx
on public.user_config_versions(user_uuid, bundle_revision_uuid);

create index user_pipeline_runs_bundle_idx
on public.user_pipeline_runs(user_uuid, config_bundle_revision_uuid)
where config_bundle_revision_uuid is not null;

create index skill_alias_catalog_canonical_idx
on public.skill_alias_catalog(normalized_canonical_skill);

create index skill_alias_catalog_alias_idx
on public.skill_alias_catalog(normalized_alias);

create index skill_alias_catalog_category_industry_idx
on public.skill_alias_catalog(category, industry);

alter table public.config_bundle_revisions enable row level security;
alter table public.config_bundle_revisions force row level security;
alter table public.skill_alias_catalog enable row level security;
alter table public.skill_alias_catalog force row level security;

create policy config_bundle_revisions_self_or_admin_select
on public.config_bundle_revisions
for select
to authenticated
using (
    (user_uuid = public.current_app_user_uuid() and public.is_current_user_active())
    or public.is_current_user_admin()
);

-- The catalog is platform-owned. Normal users receive only sanitized results
-- through authenticated API endpoints; direct table access remains Admin-only.
create policy skill_alias_catalog_admin_select
on public.skill_alias_catalog
for select
to authenticated
using (public.is_current_user_admin());

revoke all on table public.config_bundle_revisions from anon, authenticated;
revoke all on table public.skill_alias_catalog from anon, authenticated;

grant select on table public.config_bundle_revisions to authenticated;
grant select on table public.skill_alias_catalog to authenticated;
grant select (config_bundle_revision_uuid) on public.user_pipeline_runs to authenticated;

grant all on table public.config_bundle_revisions to service_role;
grant all on table public.skill_alias_catalog to service_role;

comment on table public.config_bundle_revisions is
    'Append-only logical Settings revisions joining all three generated configuration documents.';
comment on column public.config_bundle_revisions.compiled_configs is
    'Exact validated effective configs for deterministic restore; nullable only for legacy/default backfills.';
comment on table public.skill_alias_catalog is
    'Shared, versioned-by-metadata alias knowledge reused across users before pipeline execution.';
comment on column public.user_pipeline_runs.config_bundle_revision_uuid is
    'Nullable for legacy runs; identifies the coherent Settings bundle used to create the immutable snapshot.';
