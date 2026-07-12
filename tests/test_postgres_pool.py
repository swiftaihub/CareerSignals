from types import SimpleNamespace

import pytest

from packages.careersignal_core.storage import postgres_pool


class _Secret:
    def get_secret_value(self) -> str:
        return "postgresql://example.invalid/database"


class _FakeConnectionPool:
    instances = []

    def __init__(self, **_kwargs):
        self.closed = True
        self.number = len(self.instances)
        self.instances.append(self)

    def open(self, *, wait: bool) -> None:
        assert wait is True
        if self.number == 0:
            raise RuntimeError("database is still starting")
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_pool_recreates_psycopg_pool_after_failed_open(monkeypatch):
    _FakeConnectionPool.instances = []
    monkeypatch.setattr(postgres_pool, "ConnectionPool", _FakeConnectionPool)
    settings = SimpleNamespace(
        database_url=_Secret(),
        postgres_pool_min_size=1,
        postgres_pool_max_size=2,
    )
    pool = postgres_pool.PostgresPool(settings)

    with pytest.raises(RuntimeError, match="still starting"):
        pool.open()

    pool.open()

    assert len(_FakeConnectionPool.instances) == 2
    assert pool._pool is _FakeConnectionPool.instances[1]
    assert pool._pool.closed is False
