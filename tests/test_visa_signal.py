from __future__ import annotations

from src.config.loader import load_configs
from src.processing.visa_signal import detect_visa_signal


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
