"""Rule-based skill extraction."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.schemas import Candidate, SkillTaxonomyConfig
from src.utils.text_cleaning import clean_text

PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "bonus",
    "plus",
    "desired",
    "ideally",
)
REQUIRED_MARKERS = (
    "required",
    "requirements",
    "must have",
    "need",
    "needs",
    "you have",
    "qualified",
    "qualifications",
    "experience with",
    "proficiency",
    "strong",
)


@dataclass(frozen=True)
class SkillPattern:
    canonical: str
    aliases: tuple[str, ...]
    skill_group: str
    in_candidate_profile: bool


@dataclass(frozen=True)
class SkillExtractionResult:
    required_skills: list[str]
    preferred_skills: list[str]
    all_extracted_skills: list[str]


def _alias_regex(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.strip())
    escaped = re.sub(r"\\\s+", r"[\\s/\\-]+", escaped)
    if alias.strip().casefold() == "r":
        pattern = rf"(?<![A-Za-z0-9+#.]){escaped}(?![A-Za-z0-9+#.])"
    else:
        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
    return re.compile(pattern, flags=re.IGNORECASE)


def _contains_alias(text: str, aliases: tuple[str, ...]) -> bool:
    return any(_alias_regex(alias).search(text) for alias in aliases if alias.strip())


def build_skill_patterns(
    candidate: Candidate,
    taxonomy: SkillTaxonomyConfig,
) -> list[SkillPattern]:
    """Build canonical skill patterns from candidate skills and taxonomy aliases."""

    candidate_group_lookup = candidate.skill_group_lookup()
    records: dict[str, dict[str, object]] = {}

    for group, skills in candidate.skills.items():
        for skill in skills:
            key = skill.casefold()
            records.setdefault(
                key,
                {
                    "canonical": skill,
                    "aliases": set(),
                    "skill_group": group,
                    "in_candidate_profile": True,
                },
            )
            records[key]["aliases"].add(skill)  # type: ignore[index, union-attr]

    for alias_config in taxonomy.skill_aliases.values():
        canonical = alias_config.canonical
        key = canonical.casefold()
        in_candidate = key in candidate_group_lookup
        record = records.setdefault(
            key,
            {
                "canonical": canonical,
                "aliases": set(),
                "skill_group": candidate_group_lookup.get(key, "Market Skill"),
                "in_candidate_profile": in_candidate,
            },
        )
        record["canonical"] = canonical
        record["aliases"].add(canonical)  # type: ignore[index, union-attr]
        for alias in alias_config.aliases:
            record["aliases"].add(alias)  # type: ignore[index, union-attr]
        if in_candidate:
            record["skill_group"] = candidate_group_lookup[key]
            record["in_candidate_profile"] = True

    patterns = [
        SkillPattern(
            canonical=str(record["canonical"]),
            aliases=tuple(sorted(record["aliases"], key=str.casefold)),  # type: ignore[arg-type]
            skill_group=str(record["skill_group"]),
            in_candidate_profile=bool(record["in_candidate_profile"]),
        )
        for record in records.values()
    ]
    return sorted(patterns, key=lambda item: item.canonical.casefold())


def _sentences(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"(?<=[.!?;])\s+|\n+", text) if segment.strip()]


class RuleBasedSkillExtractor:
    """Deterministic MVP skill extractor with an interface ready for replacement."""

    def __init__(self, candidate: Candidate, taxonomy: SkillTaxonomyConfig) -> None:
        self.patterns = build_skill_patterns(candidate, taxonomy)

    def extract(self, description: str) -> SkillExtractionResult:
        source = clean_text(description)
        if not source:
            return SkillExtractionResult([], [], [])

        required: set[str] = set()
        preferred: set[str] = set()
        all_skills: set[str] = set()
        sentences = _sentences(source)

        for pattern in self.patterns:
            if not _contains_alias(source, pattern.aliases):
                continue
            all_skills.add(pattern.canonical)

            matching_sentences = [
                sentence for sentence in sentences if _contains_alias(sentence, pattern.aliases)
            ]
            joined = " ".join(matching_sentences).casefold()
            is_preferred = any(marker in joined for marker in PREFERRED_MARKERS)
            is_required = any(marker in joined for marker in REQUIRED_MARKERS)

            if is_preferred:
                preferred.add(pattern.canonical)
            if is_required or not is_preferred:
                required.add(pattern.canonical)

        return SkillExtractionResult(
            required_skills=sorted(required, key=str.casefold),
            preferred_skills=sorted(preferred, key=str.casefold),
            all_extracted_skills=sorted(all_skills, key=str.casefold),
        )


def extract_skills(
    description: str,
    candidate: Candidate,
    taxonomy: SkillTaxonomyConfig,
) -> SkillExtractionResult:
    """Convenience wrapper for rule-based skill extraction."""

    return RuleBasedSkillExtractor(candidate, taxonomy).extract(description)
