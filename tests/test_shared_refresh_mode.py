from src.pipelines.shared_connector_refresh import _uses_motherduck_analytics


def test_postgres_serving_mode_uses_motherduck_dbt_for_supported_targets(monkeypatch) -> None:
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "configured")

    for target in ("dev", "prod"):
        monkeypatch.setenv("DBT_TARGET", target)
        assert _uses_motherduck_analytics("postgres") is True


def test_postgres_serving_mode_rejects_unknown_dbt_target(monkeypatch) -> None:
    monkeypatch.setenv("DBT_TARGET", "unknown")
    monkeypatch.setenv("MOTHERDUCK_TOKEN", "configured")

    assert _uses_motherduck_analytics("postgres") is False


def test_local_mode_without_motherduck_configuration_stays_local(monkeypatch) -> None:
    monkeypatch.setenv("DBT_TARGET", "local")
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)

    assert _uses_motherduck_analytics("local") is False
