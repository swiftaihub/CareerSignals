"""Lazy psycopg connection pool used by API, worker, scheduler, and scripts."""

from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from threading import Lock
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from packages.careersignal_core.settings import AppSettings, SettingsError, get_settings


class PostgresPool:
    """Small wrapper that avoids opening network connections during module import."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or get_settings()
        connection_string = self.settings.database_url.get_secret_value()
        if not connection_string:
            raise SettingsError("DATABASE_URL is required for PostgreSQL access")
        self._connection_string = connection_string
        self._pool_lock = Lock()
        self._open_attempted = False
        self._pool = self._new_pool()

    def _new_pool(self) -> ConnectionPool:
        return ConnectionPool(
            conninfo=self._connection_string,
            min_size=self.settings.postgres_pool_min_size,
            max_size=self.settings.postgres_pool_max_size,
            open=False,
            kwargs={"row_factory": dict_row, "autocommit": False},
            name="careersignals",
        )

    def open(self) -> None:
        if not self._pool.closed:
            return
        with self._pool_lock:
            if not self._pool.closed:
                return
            # psycopg pools cannot be reopened after close(). An unsuccessful
            # initial open can also leave the object permanently closed, so a
            # later request must replace it rather than reuse it.
            if self._open_attempted:
                self._pool = self._new_pool()
            self._open_attempted = True
            self._pool.open(wait=True)

    def close(self) -> None:
        if not self._pool.closed:
            self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        self.open()
        with self._pool.connection() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connection() as connection:
            with connection.transaction():
                yield connection


@lru_cache(maxsize=1)
def get_postgres_pool() -> PostgresPool:
    return PostgresPool()


def close_postgres_pool() -> None:
    if get_postgres_pool.cache_info().currsize:
        get_postgres_pool().close()
        get_postgres_pool.cache_clear()
