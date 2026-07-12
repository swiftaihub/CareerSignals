"""Cross-process PostgreSQL advisory locks."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from psycopg import Connection

from packages.careersignal_core.storage.postgres_pool import PostgresPool, get_postgres_pool


class LockUnavailableError(RuntimeError):
    pass


@dataclass
class HeldAdvisoryLock:
    connection: Connection[Any]
    name: str


class AdvisoryLockManager:
    def __init__(self, pool: PostgresPool | None = None) -> None:
        self.pool = pool or get_postgres_pool()

    @contextmanager
    def acquire(self, name: str, *, wait: bool = True) -> Iterator[HeldAdvisoryLock]:
        """Hold a session-scoped lock for the complete external operation."""

        with self.pool.connection() as connection:
            if wait:
                connection.execute("select pg_advisory_lock(hashtextextended(%s, 0))", [name])
                acquired = True
            else:
                row = connection.execute(
                    "select pg_try_advisory_lock(hashtextextended(%s, 0)) as acquired", [name]
                ).fetchone()
                acquired = bool(row["acquired"])
            if not acquired:
                raise LockUnavailableError(f"Advisory lock is already held: {name}")
            try:
                yield HeldAdvisoryLock(connection=connection, name=name)
            finally:
                connection.execute("select pg_advisory_unlock(hashtextextended(%s, 0))", [name])

    @contextmanager
    def acquire_writer_slot(self, max_concurrency: int) -> Iterator[HeldAdvisoryLock]:
        """Acquire one of a fixed number of MotherDuck writer slots."""

        with self.pool.connection() as connection:
            selected: str | None = None
            for slot in range(max_concurrency):
                name = f"careersignals:motherduck-writer:{slot}"
                row = connection.execute(
                    "select pg_try_advisory_lock(hashtextextended(%s, 0)) as acquired", [name]
                ).fetchone()
                if bool(row["acquired"]):
                    selected = name
                    break
            if selected is None:
                raise LockUnavailableError("All configured MotherDuck writer slots are busy")
            try:
                yield HeldAdvisoryLock(connection=connection, name=selected)
            finally:
                connection.execute("select pg_advisory_unlock(hashtextextended(%s, 0))", [selected])
