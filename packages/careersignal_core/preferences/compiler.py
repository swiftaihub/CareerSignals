"""Compile friendly preferences into the three existing strict config documents."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Iterable, Mapping

from packages.careersignal_core.preferences.models import (
    GeneratedPreview,
    GeneratedSearchTitle,
    MatchPriorities,
    PreferencesPayload,
)
from packages.careersignal_core.preferences.normalization import slugify
from packages.careersignal_core.preferences.skill_aliases import SkillAliasService
from packages.careersignal_core.preferences.title_expansion import JobTitleExpansionService
from src.config.loader import CONFIG_TYPES, load_default_config, validate_user_config


PREFERENCES_GENERATOR_VERSION = "preferences-compiler-v1"
BACKEND_EXCEL_FILE = "outputs/job_search_tracker.xlsx"

WORK_ARRANGEMENT_SYSTEM_VALUES = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on_site": "on-site",
}
EMPLOYMENT_TYPE_SYSTEM_VALUES = {
    "full_time": "full-time",
    "part_time": "part-time",
    "contract": "contract",
    "temporary": "temporary",
    "internship": "internship",
    "apprenticeship": "apprenticeship",
    "freelance": "freelance",
    "other": "other",
}


class PreferencesCompileError(ValueError):
    pass


def _defaults() -> dict[str, dict[str, Any]]:
    return {config_type: load_default_config(config_type) for config_type in CONFIG_TYPES}


def _validated_base(base_configs: Mapping[str, Mapping[str, Any]] | None) -> dict[str, dict[str, Any]]:
    defaults = _defaults()
    if not base_configs:
        return defaults
    return {
        config_type: validate_user_config(
            config_type,
            base_configs.get(config_type, defaults[config_type]),
        )
        for config_type in CONFIG_TYPES
    }


def sparse_override(default: Any, effective: Any) -> Any:
    """Return the minimal recursive override, retaining explicit mapping clears."""

    if isinstance(default, Mapping) and isinstance(effective, Mapping):
        output: dict[str, Any] = {}
        for key in effective:
            if key not in default:
                output[key] = deepcopy(effective[key])
                continue
            difference = sparse_override(default[key], effective[key])
            if difference is not None:
                output[key] = difference
        return output or None
    if default != effective:
        return deepcopy(effective)
    return None


def _unique_key(label: str, existing: Mapping[str, Any]) -> str:
    base = slugify(label)
    if base not in existing:
        return base
    index = 2
    while f"{base}_{index}" in existing:
        index += 1
    return f"{base}_{index}"


def _candidate_skill_groups(
    preferences: PreferencesPayload,
    default_candidate: Mapping[str, Any],
) -> dict[str, list[str]]:
    # Empty the repository's sample groups explicitly so merge_config cannot
    # resurrect starter skills the user did not choose.
    groups: dict[str, list[str]] = {
        str(group): [] for group in (default_candidate.get("skills") or {})
    }
    display_to_key: dict[str, str] = {}
    for skill in preferences.skills:
        display_category = skill.category or "General"
        category_key = display_to_key.get(display_category.casefold())
        if category_key is None:
            desired = slugify(display_category, fallback="general")
            if desired in groups and groups[desired]:
                desired = _unique_key(display_category, groups)
            category_key = desired
            display_to_key[display_category.casefold()] = category_key
            groups.setdefault(category_key, [])
        if skill.name.casefold() not in {value.casefold() for value in groups[category_key]}:
            groups[category_key].append(skill.name)
    return groups


class PreferencesCompiler:
    version = PREFERENCES_GENERATOR_VERSION

    def __init__(
        self,
        *,
        title_expander: JobTitleExpansionService | None = None,
        alias_service: SkillAliasService | None = None,
    ) -> None:
        self.title_expander = title_expander or JobTitleExpansionService()
        self.alias_service = alias_service or SkillAliasService()

    @property
    def generator_version(self) -> str:
        return "+".join((self.version, self.title_expander.version, self.alias_service.version))

    def compile(
        self,
        preferences: PreferencesPayload,
        *,
        base_configs: Mapping[str, Mapping[str, Any]] | None = None,
        alias_catalog: Mapping[str, Any] | None = None,
        observed_titles: Mapping[str, Iterable[str]] | None = None,
    ) -> dict[str, Any]:
        if not preferences.search_preferences.job_titles:
            raise PreferencesCompileError("At least one job title is required before preferences can be saved")

        defaults = _defaults()
        base = _validated_base(base_configs)
        candidate_config = deepcopy(base["candidate_profile"])
        jobs_config = deepcopy(base["jobs_config"])

        title_previews: list[GeneratedSearchTitle] = []
        job_categories: list[dict[str, Any]] = []
        observed_titles = observed_titles or {}
        search = preferences.search_preferences
        for title in search.job_titles:
            variants = self.title_expander.expand(
                title,
                observed_titles=observed_titles.get(title, ()),
            )
            title_previews.append(GeneratedSearchTitle(title=title, variations=variants))
            job_categories.append(
                {
                    "category_name": title,
                    "search_titles": variants,
                    "industries": list(search.industries),
                    "seniority": list(search.seniority),
                }
            )

        aliases = self.alias_service.generate(preferences.skills, catalog=alias_catalog)
        default_taxonomy = deepcopy(defaults["skill_taxonomy"])
        taxonomy_entries: dict[str, Any] = dict(default_taxonomy.get("skill_aliases") or {})
        for alias in aliases:
            matching_key = next(
                (
                    key
                    for key, value in taxonomy_entries.items()
                    if str((value or {}).get("canonical", "")).casefold() == alias.canonical.casefold()
                ),
                None,
            )
            key = matching_key or _unique_key(alias.canonical, taxonomy_entries)
            taxonomy_entries[key] = {
                "canonical": alias.canonical,
                "aliases": list(alias.aliases),
            }

        candidate = candidate_config.setdefault("candidate", {})
        candidate["target_titles"] = list(search.job_titles)
        candidate["target_industries"] = list(search.industries)
        candidate.setdefault("required_preferences", {})["work_arrangement"] = [
            WORK_ARRANGEMENT_SYSTEM_VALUES[value] for value in search.work_arrangements
        ]
        candidate["salary_expectation"] = {
            "min_base_salary": search.compensation.minimum_salary or 0,
            "preferred_base_salary": search.compensation.preferred_salary or 0,
        }
        candidate["skills"] = _candidate_skill_groups(
            preferences,
            defaults["candidate_profile"].get("candidate") or {},
        )

        filters = jobs_config.setdefault("global_filters", {})
        filters.update(
            {
                "country": search.country,
                "locations": list(search.locations),
                "work_type": [WORK_ARRANGEMENT_SYSTEM_VALUES[value] for value in search.work_arrangements],
                "employment_type": [EMPLOYMENT_TYPE_SYSTEM_VALUES[value] for value in search.employment_types],
                "visa_preferences": list(search.visa_preferences),
                "excluded_companies": list(search.excluded_companies),
                "excluded_titles": list(search.excluded_titles),
            }
        )
        jobs_config["job_categories"] = job_categories
        jobs_config["ranking_weights"] = {
            key: value / 100 for key, value in preferences.match_priorities.model_dump().items()
        }
        output = jobs_config.setdefault("output", {})
        output["excel_file"] = BACKEND_EXCEL_FILE
        output.setdefault("top_match_threshold", defaults["jobs_config"]["output"]["top_match_threshold"])

        effective_configs = {
            "candidate_profile": validate_user_config("candidate_profile", candidate_config),
            "jobs_config": validate_user_config("jobs_config", jobs_config),
            "skill_taxonomy": validate_user_config(
                "skill_taxonomy", {"skill_aliases": taxonomy_entries}
            ),
        }
        compiled_overrides = {
            config_type: sparse_override(defaults[config_type], effective_configs[config_type]) or {}
            for config_type in CONFIG_TYPES
        }

        warnings: list[str] = []
        compensation = search.compensation
        if compensation.currency != "USD" or compensation.period != "annual":
            warnings.append(
                "Salary currency and period are saved exactly as entered, but the current matching pipeline "
                "does not perform currency or pay-period conversion."
            )
        if any(alias.confidence < 0.75 for alias in aliases):
            warnings.append("Low-confidence skill aliases were omitted from the generated taxonomy.")

        preview = GeneratedPreview(
            search_titles=title_previews,
            skill_aliases=aliases,
            derived_candidate_profile={
                "target_titles": list(search.job_titles),
                "target_industries": list(search.industries),
                "work_arrangements": list(search.work_arrangements),
                "minimum_salary": compensation.minimum_salary,
                "preferred_salary": compensation.preferred_salary,
            },
        )
        return {
            "effective_configs": effective_configs,
            "compiled_overrides": compiled_overrides,
            "generated_preview": preview,
            "warnings": warnings,
            "generator_version": self.generator_version,
            "catalog_entries": [
                {
                    "canonical_skill": alias.canonical,
                    "aliases": list(alias.aliases),
                    "category": alias.category,
                    "source": alias.source,
                    "confidence": alias.confidence,
                    "generator_version": self.alias_service.version,
                }
                for alias in aliases
            ],
        }


def normalized_priorities(weights: Mapping[str, Any]) -> MatchPriorities:
    """Normalize legacy arbitrary positive weights to exact integer percentages."""

    keys = tuple(MatchPriorities.model_fields)
    values = [max(0.0, float(weights.get(key, 0) or 0)) for key in keys]
    total = sum(values)
    if total <= 0:
        return MatchPriorities()
    exact = [value / total * 100 for value in values]
    floors = [math.floor(value) for value in exact]
    remainder = 100 - sum(floors)
    order = sorted(range(len(keys)), key=lambda index: (-(exact[index] - floors[index]), index))
    for index in order[:remainder]:
        floors[index] += 1
    return MatchPriorities(**dict(zip(keys, floors)))
