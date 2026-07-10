"""Visa sponsorship and work-authorization signal detection."""

from __future__ import annotations

from dataclasses import dataclass
import re

from src.config.schemas import VisaKeywords
from src.utils.text_cleaning import clean_text

SPONSORSHIP_AVAILABLE = "Sponsorship Available"
NO_SPONSORSHIP = "No Sponsorship"
US_CITIZENSHIP_REQUIRED = "U.S. Citizenship Required"
PERMANENT_WORK_AUTHORIZATION_REQUIRED = "Permanent Work Authorization Required"
UNKNOWN_STATUS = "Unknown"

EVIDENCE_LIMIT = 260


@dataclass(frozen=True)
class VisaClassification:
    visa_signal: str
    visa_status: str
    visa_evidence: str | None
    visa_confidence: str


PATTERN_FLAGS = re.IGNORECASE

CITIZENSHIP_PATTERNS = (
    r"\b(?:u\.?\s*s\.?|united states)\s+citizenship\s+(?:is\s+)?required\b",
    r"\bthis position requires\s+(?:u\.?\s*s\.?|united states)\s+citizenship\b",
    r"\b(?:must|need|needs|required to|requires?)\s+(?:be\s+)?(?:a\s+)?(?:u\.?\s*s\.?|united states)\s+citizen\b",
    r"\b(?:u\.?\s*s\.?|united states)\s+citizen(?:s)?\s+only\b",
    r"\bonly\s+(?:u\.?\s*s\.?|united states)\s+citizens?\s+(?:will be considered|may apply|are eligible|eligible)\b",
    r"\bcitizen(?:ship)?\s+or\s+permanent\s+resident\s+only\b",
)

NO_SPONSORSHIP_PATTERNS = (
    r"\bvisa sponsorship\s+(?:is\s+)?(?:not available|not provided|unavailable)\b",
    r"\bvisa sponsorship\s+will\s+not\s+be\s+provided\b",
    r"\b(?:we|company|employer|client|this role|this position|organization)\s+(?:do not|does not|cannot|can't|can not|will not|won't)\s+(?:provide\s+)?sponsor(?:ship)?\b",
    r"\b(?:we|company|employer|client|this role|this position|organization)\s+(?:are|is)\s+unable\s+to\s+(?:provide\s+)?sponsor(?:ship)?\b",
    r"\bno\s+(?:visa|h[-\s]?1b|immigration|employment(?:-based)?\s+immigration)?\s*sponsorship\b",
    r"\bnot eligible for sponsorship\b",
    r"\bwill not sponsor\b.*\b(?:now|future)\b",
    r"\bunable to provide sponsorship\b.*\b(?:now|future)\b",
    r"\bcannot provide sponsorship\b",
    r"\bmust not require\b.*\b(?:current|future|h[-\s]?1b|visa)?\s*sponsorship\b",
    r"\bmust be authorized to work\b.*\bwithout\b.*\bsponsorship\b",
    r"\bwithout\s+(?:current\s+or\s+future\s+)?(?:visa|h[-\s]?1b|immigration)?\s*sponsorship\b",
    r"\bdoes not sponsor applicants for work visas\b",
)

PERMANENT_AUTH_PATTERNS = (
    r"\bmust\s+(?:have|possess|maintain)\s+permanent\s+(?:unrestricted\s+)?(?:u\.?\s*s\.?\s+)?work authorization\b",
    r"\bmust\s+(?:have|possess|maintain)\s+unrestricted\s+(?:u\.?\s*s\.?\s+)?work authorization\b",
    r"\bpermanent\s+unrestricted\s+authorization\s+to\s+work\s+in\s+the\s+u\.?\s*s\.?\b",
    r"\bunrestricted\s+(?:u\.?\s*s\.?\s+)?work authorization\s+(?:is\s+)?required\b",
    r"\bpermanent\s+(?:u\.?\s*s\.?\s+)?work authorization\s+(?:is\s+)?required\b",
)

POSITIVE_PATTERNS = (
    r"\bvisa sponsorship\s+(?:is\s+)?(?:available|provided)\b",
    r"\bvisa sponsorship\s+will\s+be\s+provided\b",
    r"\bh[-\s]?1b sponsorship\s+(?:is\s+)?(?:available|provided)\b",
    r"\bwe\s+(?:do\s+)?sponsor\s+(?:employment\s+)?visas\b",
    r"\bwe\s+will\s+sponsor\s+qualified candidates\b",
    r"\bemployment(?:-based)?\s+immigration\s+sponsorship\s+(?:is\s+)?available\b",
    r"\bimmigration sponsorship\s+(?:is\s+)?available\b",
    r"\bprovide\s+h[-\s]?1b sponsorship\b",
)


def _normalize_for_matching(value: str) -> str:
    text = clean_text(value)
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("‐", "-").replace("‑", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def _split_evidence_units(text: str) -> list[str]:
    clean = _normalize_for_matching(text)
    if not clean:
        return []
    clean = re.sub(r"\bU\.?\s*S\.?(?=\s|$)", "US", clean, flags=PATTERN_FLAGS)
    units = re.split(r"(?<=[.!?])\s+|;\s+|\n+", clean)
    return [unit.strip(" -") for unit in units if unit.strip(" -")]


def _evidence_excerpt(value: str) -> str:
    text = clean_text(value)
    if len(text) <= EVIDENCE_LIMIT:
        return text
    return f"{text[: EVIDENCE_LIMIT - 3].rstrip()}..."


def _first_pattern_match(units: list[str], patterns: tuple[str, ...]) -> str | None:
    for unit in units:
        normalized = _normalize_for_matching(unit)
        if any(re.search(pattern, normalized, flags=PATTERN_FLAGS) for pattern in patterns):
            return _evidence_excerpt(unit)
    return None


def _keyword_fallback(units: list[str], visa_keywords: VisaKeywords) -> VisaClassification | None:
    negative_keywords = [keyword for keyword in visa_keywords.negative if len(keyword.strip()) >= 8]
    positive_keywords = [
        keyword
        for keyword in visa_keywords.positive
        if keyword.strip().casefold() not in {"sponsor", "h-1b", "h1b"}
    ]

    for unit in units:
        normalized = _normalize_for_matching(unit).casefold()
        if any(keyword.casefold() in normalized for keyword in negative_keywords):
            return VisaClassification("Negative", NO_SPONSORSHIP, _evidence_excerpt(unit), "Medium")

    for unit in units:
        normalized = _normalize_for_matching(unit).casefold()
        if any(keyword.casefold() in normalized for keyword in positive_keywords):
            return VisaClassification("Positive", SPONSORSHIP_AVAILABLE, _evidence_excerpt(unit), "Medium")

    return None


def classify_visa_signal(description: str | None, visa_keywords: VisaKeywords) -> VisaClassification:
    """Return structured visa sponsorship classification with deterministic precedence."""

    units = _split_evidence_units(description or "")
    if not units:
        return VisaClassification("Unknown", UNKNOWN_STATUS, None, "Low")

    citizenship_evidence = _first_pattern_match(units, CITIZENSHIP_PATTERNS)
    if citizenship_evidence:
        return VisaClassification("Negative", US_CITIZENSHIP_REQUIRED, citizenship_evidence, "High")

    no_sponsorship_evidence = _first_pattern_match(units, NO_SPONSORSHIP_PATTERNS)
    if no_sponsorship_evidence:
        return VisaClassification("Negative", NO_SPONSORSHIP, no_sponsorship_evidence, "High")

    permanent_auth_evidence = _first_pattern_match(units, PERMANENT_AUTH_PATTERNS)
    if permanent_auth_evidence:
        return VisaClassification(
            "Negative",
            PERMANENT_WORK_AUTHORIZATION_REQUIRED,
            permanent_auth_evidence,
            "High",
        )

    positive_evidence = _first_pattern_match(units, POSITIVE_PATTERNS)
    if positive_evidence:
        return VisaClassification("Positive", SPONSORSHIP_AVAILABLE, positive_evidence, "High")

    fallback = _keyword_fallback(units, visa_keywords)
    if fallback:
        return fallback

    return VisaClassification("Unknown", UNKNOWN_STATUS, None, "Low")


def detect_visa_signal(description: str | None, visa_keywords: VisaKeywords) -> str:
    """Classify visa-sponsorship signal as Positive, Negative, or Unknown."""

    return classify_visa_signal(description, visa_keywords).visa_signal
