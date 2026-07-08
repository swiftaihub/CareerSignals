"""Stable hashing helpers."""

from __future__ import annotations

import hashlib


def stable_hash(*parts: object, length: int = 16) -> str:
    """Generate a stable, compact SHA-256 hash from the provided parts."""

    normalized = "||".join("" if part is None else str(part).strip().casefold() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:length]
