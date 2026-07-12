"""Safe PostgreSQL query helpers.

Callers provide static SQL and bound parameters. This module intentionally has no
API that accepts user-supplied SQL fragments.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterable, Iterator, Mapping, Sequence

from psycopg import Connection

from packages.careersignal_core.storage.postgres_pool import PostgresPool, get_postgres_pool

Params = Sequence[Any] | Mapping[str, Any] | None


class PostgresStore:
    def __init__(self, pool: PostgresPool | None = None) -> None:
        self.pool = pool or get_postgres_pool()

    def fetch_one(self, statement: str, params: Params = None) -> dict[str, Any] | None:
        with self.pool.connection() as connection:
            row = connection.execute(statement, params).fetchone()
            return dict(row) if row is not None else None

    def fetch_all(self, statement: str, params: Params = None) -> list[dict[str, Any]]:
        with self.pool.connection() as connection:
            return [dict(row) for row in connection.execute(statement, params).fetchall()]

    def execute(self, statement: str, params: Params = None) -> int:
        with self.pool.transaction() as connection:
            cursor = connection.execute(statement, params)
            return cursor.rowcount

    def execute_many(self, statement: str, rows: Iterable[Sequence[Any]]) -> int:
        materialized = list(rows)
        if not materialized:
            return 0
        with self.pool.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(statement, materialized)
                return cursor.rowcount

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.pool.transaction() as connection:
            yield connection
