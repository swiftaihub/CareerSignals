from __future__ import annotations

import pytest

from packages.careersignal_core.settings import AppSettings, SettingsError


def _settings(**values: object) -> AppSettings:
    return AppSettings(_env_file=None, **values)


def test_worker_configuration_does_not_require_supabase_url() -> None:
    settings = _settings(
        CAREERSIGNAL_SAAS_MODE=True,
        DATABASE_URL="postgresql://runtime.invalid/database",
        MOTHERDUCK_TOKEN="worker-token",
        SUPABASE_URL="",
    )

    settings.require_worker_configuration()


def test_worker_configuration_requires_database_and_motherduck() -> None:
    settings = _settings(
        CAREERSIGNAL_SAAS_MODE=True,
        DATABASE_URL="",
        MOTHERDUCK_TOKEN="",
    )

    with pytest.raises(SettingsError, match="DATABASE_URL, MOTHERDUCK_TOKEN"):
        settings.require_worker_configuration()


def test_scheduler_configuration_only_requires_database() -> None:
    settings = _settings(
        CAREERSIGNAL_SAAS_MODE=True,
        DATABASE_URL="postgresql://runtime.invalid/database",
        SUPABASE_URL="",
    )

    settings.require_scheduler_configuration()


def test_scheduler_configuration_requires_database() -> None:
    settings = _settings(CAREERSIGNAL_SAAS_MODE=True, DATABASE_URL="")

    with pytest.raises(SettingsError, match="scheduler settings: DATABASE_URL"):
        settings.require_scheduler_configuration()


def test_api_configuration_still_requires_supabase_url_and_jwks() -> None:
    settings = _settings(
        CAREERSIGNAL_SAAS_MODE=True,
        DATABASE_URL="postgresql://runtime.invalid/database",
        SUPABASE_URL="",
        SUPABASE_JWKS_URL="",
    )

    with pytest.raises(SettingsError, match="SUPABASE_URL, SUPABASE_JWKS_URL"):
        settings.require_api_configuration()
