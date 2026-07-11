from __future__ import annotations

from packages.careersignal_core.storage.postgres import PostgresStore


def get_database() -> PostgresStore:
    return PostgresStore()
