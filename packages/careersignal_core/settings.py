"""Typed, environment-driven settings shared by all CareerSignals services."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class SettingsError(RuntimeError):
    """Raised when a process starts without its required secure settings."""


class AppSettings(BaseSettings):
    """Process settings. Secret values are represented as ``SecretStr`` values."""

    model_config = SettingsConfigDict(
        env_file=(project_root() / ".env", project_root() / "apps" / "api" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    saas_mode: bool = Field(default=False, validation_alias="CAREERSIGNAL_SAAS_MODE")
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development", validation_alias="CAREERSIGNAL_ENVIRONMENT"
    )
    data_mode: Literal["local", "motherduck", "postgres"] = Field(
        default="motherduck", validation_alias="CAREERSIGNAL_DATA_MODE"
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")

    supabase_url: str = Field(default="", validation_alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", validation_alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: SecretStr = Field(
        default=SecretStr(""), validation_alias="SUPABASE_SERVICE_ROLE_KEY"
    )
    supabase_jwt_audience: str = Field(
        default="authenticated", validation_alias="SUPABASE_JWT_AUDIENCE"
    )
    supabase_jwt_issuer: str = Field(default="", validation_alias="SUPABASE_JWT_ISSUER")
    supabase_jwks_url: str = Field(default="", validation_alias="SUPABASE_JWKS_URL")
    database_url: SecretStr = Field(default=SecretStr(""), validation_alias="DATABASE_URL")
    postgres_pool_min_size: int = Field(default=1, ge=0, validation_alias="POSTGRES_POOL_MIN_SIZE")
    postgres_pool_max_size: int = Field(default=10, ge=1, validation_alias="POSTGRES_POOL_MAX_SIZE")

    admin_bootstrap_username: str = Field(
        default="admin", validation_alias="ADMIN_BOOTSTRAP_USERNAME"
    )
    admin_bootstrap_email: str = Field(default="", validation_alias="ADMIN_BOOTSTRAP_EMAIL")
    admin_bootstrap_password: SecretStr = Field(
        default=SecretStr(""), validation_alias="ADMIN_BOOTSTRAP_PASSWORD"
    )

    demo_user_uuid: str = Field(default="", validation_alias="DEMO_USER_UUID")
    demo_session_secret: SecretStr = Field(
        default=SecretStr(""), validation_alias="DEMO_SESSION_SECRET"
    )
    demo_session_ttl_minutes: int = Field(
        default=60, ge=5, le=1440, validation_alias="DEMO_SESSION_TTL_MINUTES"
    )

    connector_refresh_cron: str = Field(
        default="0 */6 * * *", validation_alias="CONNECTOR_REFRESH_CRON"
    )
    connector_refresh_timezone: str = Field(
        default="UTC", validation_alias="CONNECTOR_REFRESH_TIMEZONE"
    )
    connector_stale_after_hours: int = Field(
        default=8, ge=1, validation_alias="CONNECTOR_STALE_AFTER_HOURS"
    )
    scheduler_internal_secret: SecretStr = Field(
        default=SecretStr(""), validation_alias="SCHEDULER_INTERNAL_SECRET"
    )

    user_pipeline_daily_limit: int | None = Field(
        default=None, ge=1, validation_alias="USER_PIPELINE_DAILY_LIMIT"
    )
    user_pipeline_max_concurrency: int = Field(
        default=1, ge=1, validation_alias="USER_PIPELINE_MAX_CONCURRENCY"
    )
    user_pipeline_poll_seconds: float = Field(
        default=2.0, ge=0.25, le=60, validation_alias="USER_PIPELINE_POLL_SECONDS"
    )

    motherduck_token: SecretStr = Field(default=SecretStr(""), validation_alias="MOTHERDUCK_TOKEN")
    motherduck_database: str = Field(default="CareerSignal", validation_alias="MOTHERDUCK_DATABASE")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        return normalized if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def jwks_url(self) -> str:
        if self.supabase_jwks_url:
            return self.supabase_jwks_url
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        return ""

    @property
    def jwt_issuer(self) -> str:
        if self.supabase_jwt_issuer:
            return self.supabase_jwt_issuer.rstrip("/")
        if self.supabase_url:
            return f"{self.supabase_url.rstrip('/')}/auth/v1"
        return ""

    def require_api_configuration(self) -> None:
        if not self.saas_mode:
            return
        missing: list[str] = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.jwks_url:
            missing.append("SUPABASE_JWKS_URL")
        if not self.database_url.get_secret_value():
            missing.append("DATABASE_URL")
        if missing:
            raise SettingsError("Missing required SaaS API settings: " + ", ".join(missing))

    def require_backend_service_role(self) -> None:
        if not self.supabase_service_role_key.get_secret_value():
            raise SettingsError("SUPABASE_SERVICE_ROLE_KEY is required for this operation")


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


def bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def saas_mode() -> bool:
    return bool_env("CAREERSIGNAL_SAAS_MODE", get_settings().saas_mode)


def data_mode() -> str:
    """Return the configured serving mode while remaining monkeypatch-friendly in tests."""

    value = os.getenv("CAREERSIGNAL_DATA_MODE", get_settings().data_mode).strip().casefold()
    return value if value in {"local", "motherduck", "postgres"} else "motherduck"


def is_motherduck_mode() -> bool:
    return data_mode() == "motherduck"


def resolve_project_path(path: str | Path) -> Path:
    """Resolve repo-relative or apps/api-relative paths to an absolute path."""

    candidate = Path(path)
    if candidate.is_absolute():
        return candidate

    root = project_root()
    root_candidate = (root / candidate).resolve()
    if root_candidate.exists():
        return root_candidate

    api_candidate = (root / "apps" / "api" / candidate).resolve()
    if api_candidate.exists():
        return api_candidate

    return root_candidate


def local_data_dir() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_LOCAL_DATA_DIR", "data"))


def output_dir() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_OUTPUT_DIR", "outputs"))


def excel_path() -> Path:
    return resolve_project_path(os.getenv("CAREERSIGNAL_EXCEL_PATH", "outputs/job_search_tracker.xlsx"))


def dbt_project_dir() -> Path:
    return resolve_project_path(os.getenv("DBT_PROJECT_DIR", "dbt"))


def dbt_profiles_dir() -> Path:
    return resolve_project_path(os.getenv("DBT_PROFILES_DIR", "dbt"))
