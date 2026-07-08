"""Rule-based industry classification."""

from __future__ import annotations

from src.config.schemas import JobCategoryConfig
from src.utils.text_cleaning import clean_text

INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Health Tech": (
        "health tech",
        "digital health",
        "patient engagement",
        "clinical platform",
        "healthcare software",
        "provider analytics",
    ),
    "Healthcare": (
        "healthcare",
        "clinical",
        "patient",
        "provider",
        "care management",
        "ehr",
        "claims",
        "medical",
    ),
    "Consumer Lending": (
        "consumer lending",
        "lending",
        "loan",
        "credit card",
        "underwriting",
        "portfolio risk",
    ),
    "Fintech": (
        "fintech",
        "payments",
        "neobank",
        "financial technology",
        "fraud",
        "risk decisioning",
    ),
    "Banking": (
        "banking",
        "bank",
        "financial services",
        "deposit",
        "credit union",
        "basel",
    ),
    "Technology": (
        "technology",
        "software",
        "saas",
        "cloud",
        "ai",
        "machine learning",
        "data platform",
    ),
    "Consulting": (
        "consulting",
        "client services",
        "professional services",
        "advisory",
    ),
}

ALIASES = {
    "tech": "Technology",
    "technology": "Technology",
    "software": "Technology",
    "saas": "Technology",
    "ai": "Technology",
    "healthcare": "Healthcare",
    "health tech": "Health Tech",
    "digital health": "Health Tech",
    "banking": "Banking",
    "financial services": "Banking",
    "fintech": "Fintech",
    "consumer lending": "Consumer Lending",
    "credit risk": "Consumer Lending",
    "fraud": "Fintech",
    "consulting": "Consulting",
}


def _canonical_from_text(value: str) -> str | None:
    normalized = clean_text(value).casefold()
    if not normalized:
        return None
    if normalized in ALIASES:
        return ALIASES[normalized]
    for alias, canonical in ALIASES.items():
        if alias in normalized:
            return canonical
    return None


def classify_industry(
    category_config: JobCategoryConfig,
    company: str,
    description: str,
    raw_industry: str | None = None,
) -> str:
    """Classify a job into one of the MVP industry labels."""

    explicit = _canonical_from_text(raw_industry or "")
    if explicit:
        return explicit

    category_text = " ".join([category_config.category_name, *category_config.industries])
    source = clean_text(f"{category_text} {company} {description}").casefold()

    scores: dict[str, int] = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        scores[industry] = sum(1 for keyword in keywords if keyword in source)

    best_industry, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score > 0:
        return best_industry

    category_hint = _canonical_from_text(category_text)
    if category_hint:
        return category_hint
    return "Unknown"
