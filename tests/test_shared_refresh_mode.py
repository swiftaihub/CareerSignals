from src.pipelines.shared_connector_refresh import _uses_motherduck_analytics


def test_postgres_serving_mode_still_uses_motherduck_dbt(monkeypatch) -> None:
    monkeypatch.setenv("DBT_TARGET", "dev")
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "configured")

    assert _uses_motherduck_analytics("postgres") is True


def test_local_mode_without_motherduck_configuration_stays_local(monkeypatch) -> None:
    monkeypatch.setenv("DBT_TARGET", "local")
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)

    assert _uses_motherduck_analytics("local") is False
