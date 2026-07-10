from __future__ import annotations

from src.config.loader import load_configs
from src.processing.visa_signal import (
    NO_SPONSORSHIP,
    PERMANENT_WORK_AUTHORIZATION_REQUIRED,
    SPONSORSHIP_AVAILABLE,
    US_CITIZENSHIP_REQUIRED,
    UNKNOWN_STATUS,
    classify_visa_signal,
    detect_visa_signal,
)


def _classify(description: str | None):
    keywords = load_configs(".").candidate_profile.candidate.visa_keywords
    return classify_visa_signal(description, keywords)


def test_detect_positive_visa_signal() -> None:
    keywords = load_configs(".").candidate_profile.candidate.visa_keywords

    assert detect_visa_signal("H-1B sponsorship is available.", keywords) == "Positive"


def test_detect_negative_visa_signal_takes_priority() -> None:
    keywords = load_configs(".").candidate_profile.candidate.visa_keywords

    signal = detect_visa_signal(
        "The team can discuss visa status, but we are unable to sponsor this role.",
        keywords,
    )

    assert signal == "Negative"


def test_detect_unknown_visa_signal() -> None:
    keywords = load_configs(".").candidate_profile.candidate.visa_keywords

    assert detect_visa_signal("Benefits include health insurance and PTO.", keywords) == "Unknown"


def test_strong_negative_no_sponsorship_patterns() -> None:
    examples = [
        "We are unable to provide sponsorship now or in the future.",
        "Applicants must not require current or future H-1B sponsorship.",
        "We support employment-based immigration; however, this specific role cannot provide sponsorship.",
    ]

    for description in examples:
        result = _classify(description)
        assert result.visa_signal == "Negative"
        assert result.visa_status == NO_SPONSORSHIP
        assert result.visa_confidence == "High"
        assert result.visa_evidence


def test_citizenship_requirement_takes_highest_priority() -> None:
    examples = [
        "Only U.S. citizens will be considered for this position.",
        "This position requires U.S. citizenship due to security-clearance requirements.",
    ]

    for description in examples:
        result = _classify(description)
        assert result.visa_signal == "Negative"
        assert result.visa_status == US_CITIZENSHIP_REQUIRED
        assert result.visa_evidence


def test_permanent_work_authorization_requirement_is_negative() -> None:
    result = _classify("Candidates must possess permanent unrestricted authorization to work in the U.S.")

    assert result.visa_signal == "Negative"
    assert result.visa_status == PERMANENT_WORK_AUTHORIZATION_REQUIRED


def test_strong_positive_sponsorship_pattern() -> None:
    result = _classify("We provide H-1B sponsorship for qualified candidates.")

    assert result.visa_signal == "Positive"
    assert result.visa_status == SPONSORSHIP_AVAILABLE
    assert result.visa_evidence == "We provide H-1B sponsorship for qualified candidates."


def test_ambiguous_authorization_and_unrelated_sponsor_language_stay_unknown() -> None:
    examples = [
        "Must be legally authorized to work in the United States.",
        "Our executive sponsor supports this program.",
        "The company sponsors local technology conferences.",
    ]

    for description in examples:
        result = _classify(description)
        assert result.visa_signal == "Unknown"
        assert result.visa_status == UNKNOWN_STATUS
        assert result.visa_evidence is None


def test_mixed_capitalization_html_newlines_and_unicode_apostrophes() -> None:
    result = _classify(
        "<p>WE ARE UNABLE\nTO PROVIDE SPONSORSHIP now or in the future.</p>"
        " Candidate’s experience should include SQL."
    )

    assert result.visa_signal == "Negative"
    assert result.visa_status == NO_SPONSORSHIP
    assert "<p>" not in (result.visa_evidence or "")


def test_contradictory_sentences_use_restrictive_precedence() -> None:
    result = _classify(
        "Visa sponsorship is available for some roles. Only U.S. citizens will be considered for this position."
    )

    assert result.visa_signal == "Negative"
    assert result.visa_status == US_CITIZENSHIP_REQUIRED


def test_empty_and_missing_descriptions_are_unknown() -> None:
    for description in ("", None):
        result = _classify(description)
        assert result.visa_signal == "Unknown"
        assert result.visa_status == UNKNOWN_STATUS
        assert result.visa_confidence == "Low"
