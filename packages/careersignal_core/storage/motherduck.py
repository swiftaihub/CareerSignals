"""MotherDuck connection service."""

from __future__ import annotations

from contextlib import contextmanager
import os
from typing import Any, Iterator

import duckdb

from packages.careersignal_core.settings import is_motherduck_mode


class MotherDuckConfigurationError(RuntimeError):
    """Raised when MotherDuck mode is enabled without required configuration."""


class MotherDuckService:
    """Small wrapper around DuckDB's MotherDuck connection support."""

    def __init__(self, database: str | None = None) -> None:
        self.database = database or os.getenv("MOTHERDUCK_DATABASE", "CareerSignal")
        self.token = os.getenv("MOTHERDUCK_TOKEN")

    def ensure_configured(self) -> None:
        if is_motherduck_mode() and not self.token:
            raise MotherDuckConfigurationError(
                "CAREERSIGNAL_DATA_MODE=motherduck requires MOTHERDUCK_TOKEN in the environment."
            )

    def get_connection_string(self) -> str:
        """Return the MotherDuck connection string without exposing credentials."""

        self.ensure_configured()
        return f"md:{self.database}"

    @contextmanager
    def connect(self) -> Iterator[duckdb.DuckDBPyConnection]:
        conn = duckdb.connect(self.get_connection_string())
        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> Any:
        with self.connect() as conn:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)

    def query_df(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None):
        with self.connect() as conn:
            if params:
                return conn.execute(sql, params).fetchdf()
            return conn.execute(sql).fetchdf()
