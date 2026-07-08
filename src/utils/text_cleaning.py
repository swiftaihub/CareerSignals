"""Text normalization helpers."""

from __future__ import annotations

import html
import re
from typing import Any

WHITESPACE_RE = re.compile(r"\s+")
HTML_TAG_RE = re.compile(r"<[^>]+>")


def clean_text(value: Any) -> str:
    """Convert raw text-like input into a whitespace-normalized string."""

    if value is None:
        return ""
    text = html.unescape(str(value))
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def normalized_lower(value: Any) -> str:
    return clean_text(value).casefold()


def normalize_title(title: str) -> str:
    """Return a readable normalized title while preserving the source wording."""

    text = clean_text(title)
    text = re.sub(r"\b(remote|hybrid|onsite|on-site)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[-|]\s*$", "", text).strip(" -|")
    return WHITESPACE_RE.sub(" ", text).strip()


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_text(item) for item in value if clean_text(item)]
    if isinstance(value, tuple | set):
        return [clean_text(item) for item in value if clean_text(item)]
    text = clean_text(value)
    return [text] if text else []
