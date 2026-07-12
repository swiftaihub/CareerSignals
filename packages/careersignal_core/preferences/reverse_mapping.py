"""Backward-compatible mapping from legacy config documents to friendly preferences."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable

from packages.careersignal_core.preferences.compiler import normalized_priorities
from packages.careersignal_core.preferences.models import (
    CompensationPreferences,
    GeneratedPreview,
    GeneratedSearchTitle,
    GeneratedSkillAlias,
    PreferencesPayload,
    RevisionHistoryItem,
    RevisionMetadata,
    SearchPreferences,
    SkillPreference,
)
from packages.careersignal_core.preferences.normalization import dedupe_strings, sanitize_text
from packages.careersignal_core.preferences.skill_aliases import SkillAliasService
from packages.careersignal_core.preferences.title_expansion import JobTitleExpansionService
from src.config.loader import CONFIG_TYPES, load_default_config, validate_user_config


LEGACY_IMPORT_WARNING = (
    "These settings were imported from legacy configuration documents. Generated title and skill "
    "taxonomy values may not map perfectly to the new editor; the original revisions remain in history."
)
TAXONOMY_IMPORT_WARNING = (
    "Legacy taxonomy-only skills were imported into the unified skills list and should be reviewed "
    "before saving because taxonomy vocabulary did not always mean candidate experience."
)
UNCONFIRMED_DEFAULT_WARNING = (
    "Starter values are shown for reference but have not been confirmed as your preferences."
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def effective_configs_from_state(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = (
        state.get("effective_configs"),
        state.get("compiled_configs"),
        state.get("configs"),
        _mapping(state.get("snapshot")).get("configs"),
        _mapping(state.get("config_snapshot")).get("configs"),
    )
    for candidate in candidates:
        if isinstance(candidate, Mapping) and all(key in candidate for key in CONFIG_TYPES):
            return {
                config_type: validate_user_config(config_type, _mapping(candidate[config_type]))
                for config_type in CONFIG_TYPES
            }

    documents = state.get("documents") or state.get("config_documents")
    if isinstance(documents, Mapping):
        indexed = {
            str(key): _mapping(document).get("effective_config")
            for key, document in documents.items()
        }
        if all(indexed.get(config_type) for config_type in CONFIG_TYPES):
            return {
                config_type: validate_user_config(config_type, _mapping(indexed[config_type]))
                for config_type in CONFIG_TYPES
            }
    if isinstance(documents, Iterable) and not isinstance(documents, (str, bytes, Mapping)):
        indexed = {
            str(_mapping(document).get("config_type")): _mapping(document).get("effective_config")
            for document in documents
        }
        if all(indexed.get(config_type) for config_type in CONFIG_TYPES):
            return {
                config_type: validate_user_config(config_type, _mapping(indexed[config_type]))
                for config_type in CONFIG_TYPES
            }

    return {config_type: load_default_config(config_type) for config_type in CONFIG_TYPES}


def _override_configs_from_state(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    overrides = state.get("override_configs") or state.get("compiled_overrides")
    if isinstance(overrides, Mapping):
        return {str(key): _mapping(value) for key, value in overrides.items()}
    documents = state.get("documents") or state.get("config_documents")
    if isinstance(documents, Mapping):
        return {
            str(config_type): _mapping(
                _mapping(document).get("override_config")
                or _mapping(document).get("override_json")
            )
            for config_type, document in documents.items()
        }
    if isinstance(documents, Iterable) and not isinstance(documents, (str, bytes, Mapping)):
        return {
            str(_mapping(document).get("config_type")): _mapping(
                _mapping(document).get("override_config")
                or _mapping(document).get("override_json")
            )
            for document in documents
        }
    return {}


def _current_bundle(state: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("bundle", "current_bundle", "bundle_revision"):
        value = state.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    if state.get("bundle_revision_uuid") or state.get("preferences_json"):
        return dict(state)
    return {}


def _humanize_group(value: str) -> str:
    return sanitize_text(value.replace("_", " ").replace("-", " ")).title()


def _preview_from_configs(
    preferences: PreferencesPayload,
    configs: Mapping[str, Mapping[str, Any]],
) -> GeneratedPreview:
    jobs = _mapping(configs.get("jobs_config"))
    categories = [
        _mapping(value) for value in jobs.get("job_categories", []) if isinstance(value, Mapping)
    ]
    title_expander = JobTitleExpansionService()
    title_rows: list[GeneratedSearchTitle] = []
    for title in preferences.search_preferences.job_titles:
        configured: list[str] = []
        for category in categories:
            category_name = sanitize_text(category.get("category_name"))
            search_titles = dedupe_strings(category.get("search_titles") or [])
            if category_name.casefold() == title.casefold() or any(
                configured_title.casefold() == title.casefold() for configured_title in search_titles
            ):
                configured.extend([category_name, *search_titles])
        variations = dedupe_strings(configured) or title_expander.expand(title)
        if title.casefold() not in {value.casefold() for value in variations}:
            variations.insert(0, title)
        title_rows.append(GeneratedSearchTitle(title=title, variations=variations))

    taxonomy = _mapping(configs.get("skill_taxonomy")).get("skill_aliases") or {}
    alias_lookup: dict[str, dict[str, Any]] = {}
    if isinstance(taxonomy, Mapping):
        for raw in taxonomy.values():
            value = _mapping(raw)
            canonical = sanitize_text(value.get("canonical"))
            if canonical:
                alias_lookup[canonical.casefold()] = value
    fallback_aliases = {
        alias.canonical.casefold(): alias
        for alias in SkillAliasService().generate(preferences.skills)
    }
    skill_rows: list[GeneratedSkillAlias] = []
    for skill in preferences.skills:
        configured = alias_lookup.get(skill.name.casefold())
        if configured:
            aliases = dedupe_strings([skill.name, *(configured.get("aliases") or [])])
            skill_rows.append(
                GeneratedSkillAlias(
                    canonical=skill.name,
                    aliases=aliases,
                    category=skill.category,
                    source="legacy_taxonomy",
                    confidence=1.0,
                )
            )
        else:
            skill_rows.append(fallback_aliases[skill.name.casefold()])

    search = preferences.search_preferences
    return GeneratedPreview(
        search_titles=title_rows,
        skill_aliases=skill_rows,
        derived_candidate_profile={
            "target_titles": list(search.job_titles),
            "target_industries": list(search.industries),
            "work_arrangements": list(search.work_arrangements),
            "minimum_salary": search.compensation.minimum_salary,
            "preferred_salary": search.compensation.preferred_salary,
        },
    )


def reverse_map_legacy_configs(
    configs: Mapping[str, Mapping[str, Any]],
    *,
    confirmed: bool,
) -> tuple[PreferencesPayload, GeneratedPreview, list[str]]:
    candidate = _mapping(_mapping(configs.get("candidate_profile")).get("candidate"))
    jobs = _mapping(configs.get("jobs_config"))
    filters = _mapping(jobs.get("global_filters"))
    categories = [
        _mapping(value) for value in jobs.get("job_categories", []) if isinstance(value, Mapping)
    ]

    target_titles = dedupe_strings(candidate.get("target_titles") or [])
    job_titles = target_titles or dedupe_strings(
        category.get("category_name") for category in categories
    )
    industries = dedupe_strings(
        [
            *(candidate.get("target_industries") or []),
            *(industry for category in categories for industry in (category.get("industries") or [])),
        ]
    )
    seniority = dedupe_strings(
        level for category in categories for level in (category.get("seniority") or [])
    )

    salary = _mapping(candidate.get("salary_expectation"))
    minimum_salary = float(salary.get("min_base_salary") or 0) or None
    preferred_salary = float(salary.get("preferred_base_salary") or 0) or None

    candidate_skills: list[SkillPreference] = []
    candidate_names: set[str] = set()
    groups = _mapping(candidate.get("skills"))
    for group, values in groups.items():
        category = _humanize_group(str(group))
        for skill_name in dedupe_strings(values or []):
            key = skill_name.casefold()
            if key in candidate_names:
                continue
            candidate_names.add(key)
            candidate_skills.append(
                SkillPreference(
                    name=skill_name,
                    category=category,
                    source="candidate" if confirmed else "default",
                    confirmed=confirmed,
                )
            )

    taxonomy_only = 0
    taxonomy = _mapping(_mapping(configs.get("skill_taxonomy")).get("skill_aliases"))
    for raw in taxonomy.values():
        canonical = sanitize_text(_mapping(raw).get("canonical"))
        if not canonical or canonical.casefold() in candidate_names:
            continue
        candidate_names.add(canonical.casefold())
        taxonomy_only += 1
        candidate_skills.append(
            SkillPreference(
                name=canonical,
                category=None,
                source="taxonomy" if confirmed else "default",
                confirmed=False,
            )
        )

    work_arrangements = (
        _mapping(candidate.get("required_preferences")).get("work_arrangement")
        or filters.get("work_type")
        or []
    )
    preferences = PreferencesPayload(
        search_preferences=SearchPreferences(
            job_titles=job_titles,
            industries=industries,
            seniority=seniority,
            country=filters.get("country") or "US",
            locations=filters.get("locations") or [],
            work_arrangements=work_arrangements,
            employment_types=filters.get("employment_type") or [],
            visa_preferences=filters.get("visa_preferences") or [],
            excluded_companies=filters.get("excluded_companies") or [],
            excluded_titles=filters.get("excluded_titles") or [],
            compensation=CompensationPreferences(
                minimum_salary=minimum_salary,
                preferred_salary=preferred_salary,
                currency="USD",
                period="annual",
            ),
        ),
        skills=candidate_skills,
        skill_categories=dedupe_strings(
            skill.category for skill in candidate_skills if skill.category
        ),
        match_priorities=normalized_priorities(_mapping(jobs.get("ranking_weights"))),
    )
    warnings = [LEGACY_IMPORT_WARNING] if confirmed else [UNCONFIRMED_DEFAULT_WARNING]
    if taxonomy_only:
        warnings.append(TAXONOMY_IMPORT_WARNING)
    if minimum_salary is not None or preferred_salary is not None:
        warnings.append(
            "Legacy compensation did not store currency or pay period; USD and annual were inferred."
        )
    return preferences, _preview_from_configs(preferences, configs), warnings


def revision_metadata(state: Mapping[str, Any]) -> RevisionMetadata:
    bundle = _current_bundle(state)
    return RevisionMetadata(
        bundle_uuid=(
            bundle.get("bundle_revision_uuid")
            or bundle.get("bundle_uuid")
            or state.get("bundle_revision_uuid")
        ),
        revision=bundle.get("revision") or state.get("revision") or None,
        config_revision_map=_mapping(
            bundle.get("config_revision_map") or state.get("config_revision_map")
        ),
        generator_version=str(
            bundle.get("generator_version") or state.get("generator_version") or "preferences-v1"
        ),
        created_at=bundle.get("created_at") or state.get("created_at"),
    )


def history_items(records: Iterable[Mapping[str, Any]]) -> list[RevisionHistoryItem]:
    output: list[RevisionHistoryItem] = []
    for raw in records:
        record = _mapping(raw)
        bundle_uuid = record.get("bundle_revision_uuid") or record.get("bundle_uuid")
        if not bundle_uuid or not record.get("created_at"):
            continue
        output.append(
            RevisionHistoryItem(
                bundle_uuid=bundle_uuid,
                revision=int(record.get("revision") or 1),
                created_at=record["created_at"],
                generator_version=str(record.get("generator_version") or "preferences-v1"),
                source_ui_version=record.get("source_ui_version"),
                status=str(record.get("status") or "active"),
                is_current=bool(record.get("is_current", False)),
                warnings=list(record.get("warnings") or record.get("validation_warnings") or []),
            )
        )
    return output


def payload_from_state(
    state: Mapping[str, Any],
) -> tuple[PreferencesPayload, GeneratedPreview, list[str], bool]:
    bundle = _current_bundle(state)
    stored_preferences = (
        bundle.get("preferences_json")
        or bundle.get("preferences")
        or state.get("preferences")
    )
    if isinstance(stored_preferences, Mapping) and bool(stored_preferences):
        preferences = PreferencesPayload.model_validate(stored_preferences)
        stored_preview = (
            bundle.get("generated_preview")
            or bundle.get("generated_preview_json")
            or state.get("generated_preview")
        )
        preview = (
            GeneratedPreview.model_validate(stored_preview)
            if isinstance(stored_preview, Mapping)
            else _preview_from_configs(preferences, effective_configs_from_state(state))
        )
        return (
            preferences,
            preview,
            list(
                bundle.get("warnings")
                or bundle.get("validation_warnings")
                or state.get("validation_warnings")
                or []
            ),
            True,
        )

    configs = effective_configs_from_state(state)
    overrides = _override_configs_from_state(state)
    confirmed = any(bool(value) for value in overrides.values())
    preferences, preview, warnings = reverse_map_legacy_configs(configs, confirmed=confirmed)
    warnings.extend(list(state.get("validation_warnings") or []))
    return preferences, preview, warnings, confirmed
