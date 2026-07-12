"""Layered, deterministic skill alias generation."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from packages.careersignal_core.preferences.models import GeneratedSkillAlias, SkillPreference
from packages.careersignal_core.preferences.normalization import dedupe_strings, normalized_key, sanitize_text


SKILL_ALIAS_GENERATOR_VERSION = "skill-alias-rules-v1"

CURATED_ALIASES: dict[str, tuple[str, ...]] = {
    "artificial intelligence": ("AI",),
    "c#": ("C Sharp", "C-Sharp"),
    "c++": ("C Plus Plus", "CPP"),
    "dbt": ("data build tool",),
    "large language model": ("LLM", "large language models"),
    "llm": ("large language model", "large language models"),
    "microsoft power bi": ("Power BI", "PowerBI", "PBI"),
    "natural language processing": ("NLP",),
    "node.js": ("NodeJS", "Node JS"),
    "power bi": ("PowerBI", "Microsoft Power BI", "PBI"),
    "project management professional": ("PMP",),
    "registered nursing": ("Registered Nurse", "RN"),
    "rest api": ("REST APIs", "RESTful API"),
    "rest apis": ("REST API", "RESTful APIs"),
    "retrieval augmented generation": ("RAG", "retrieval-augmented generation"),
    "salesforce": ("Salesforce CRM",),
}


def _catalog_aliases(value: Any) -> tuple[list[str], float]:
    aliases: list[str] = []
    confidence = 1.0
    if isinstance(value, str):
        return [value], confidence
    if isinstance(value, Mapping):
        aliases.extend(value.get("aliases") or [])
        if value.get("alias"):
            aliases.append(value["alias"])
        try:
            confidence = float(value.get("confidence", 1.0))
        except (TypeError, ValueError):
            confidence = 1.0
        return aliases, confidence
    if isinstance(value, Iterable):
        for item in value:
            item_aliases, item_confidence = _catalog_aliases(item)
            aliases.extend(item_aliases)
            confidence = min(confidence, item_confidence)
    return aliases, confidence


def deterministic_aliases(canonical: str) -> list[str]:
    canonical = sanitize_text(canonical)
    aliases: list[str] = [canonical]
    aliases.extend(CURATED_ALIASES.get(canonical.casefold(), ()))

    if re.search(r"[.-]", canonical):
        punctuation_free = re.sub(r"[.-]+", " ", canonical)
        aliases.append(punctuation_free)
        compact = re.sub(r"[^A-Za-z0-9+#]+", "", canonical)
        if len(compact) >= 3:
            aliases.append(compact)

    words = canonical.split()
    if len(words) >= 2 and all(len(word) >= 2 for word in words):
        aliases.append("-".join(words))

    # Generated two-character acronyms are deliberately excluded. Curated
    # aliases may include them only when their relationship is unambiguous.
    return dedupe_strings(alias for alias in aliases if alias == canonical or len(alias) >= 3)


class SkillAliasService:
    version = SKILL_ALIAS_GENERATOR_VERSION

    def generate(
        self,
        skills: Iterable[SkillPreference],
        *,
        catalog: Mapping[str, Any] | None = None,
    ) -> list[GeneratedSkillAlias]:
        catalog = catalog or {}
        generated: list[GeneratedSkillAlias] = []
        for skill in skills:
            canonical = sanitize_text(skill.name)
            catalog_value = catalog.get(normalized_key(canonical), catalog.get(canonical, []))
            catalog_values, catalog_confidence = _catalog_aliases(catalog_value)
            safe_catalog_values = [
                alias
                for alias in dedupe_strings(catalog_values)
                if len(alias) >= 3 or alias.casefold() in CURATED_ALIASES.get(canonical.casefold(), ())
            ]
            aliases = dedupe_strings([*deterministic_aliases(canonical), *safe_catalog_values])
            generated.append(
                GeneratedSkillAlias(
                    canonical=canonical,
                    aliases=aliases,
                    category=skill.category,
                    source="catalog" if safe_catalog_values else "deterministic",
                    confidence=max(0.0, min(1.0, catalog_confidence if safe_catalog_values else 1.0)),
                )
            )
        return generated
