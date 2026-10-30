"""Application configuration.

All secrets come from the environment (or a mounted env file).  Nothing in this
module contains a usable credential.  ``SECRET_KEY`` and ``ENCRYPTION_KEY`` are
validated at startup in production mode.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- identity ---------------------------------------------------------
    APP_NAME: str = "H-Caliper"
    ENV: str = "development"
    API_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "dev-only-change-me-0123456789abcdef"
    ENCRYPTION_KEY: Optional[str] = None
    ACCESS_TOKEN_MINUTES: int = 720
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: Optional[str] = None

    # --- storage ----------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://hcaliper:hcaliper_secret@localhost:5433/hcaliper"
    WORKSPACE_ROOT: str = "/var/lib/hcaliper/workspaces"
    ALLOWED_LOCAL_REPO_ROOTS: Annotated[List[str], NoDecode] = []
    MAX_CONTEXT_CHARS: int = 60_000
    MAX_ARTIFACT_BYTES: int = 2_000_000

    # --- HTTP -------------------------------------------------------------
    CORS_ORIGINS: Annotated[List[str], NoDecode] = ["http://localhost:3001", "http://localhost:8080"]
    RATE_LIMIT_PER_MINUTE: int = 240
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    TRUSTED_PROXY_COUNT: int = 0

    # --- providers --------------------------------------------------------
    PROVIDER_CONNECT_TIMEOUT: float = 10.0
    PROVIDER_REQUEST_TIMEOUT: float = 300.0
    PROVIDER_MAX_RESPONSE_BYTES: int = 8_000_000
    ALLOW_PRIVATE_PROVIDER_HOSTS: bool = True
    OPENCODE_COMMAND: str = "opencode"
    CODEX_COMMAND: str = "codex"
    ANTIGRAVITY_COMMAND: str = "agy"
    AGENT_TIMEOUT_SECONDS: int = 1800
    AGENT_MAX_OUTPUT_CHARS: int = 200_000

    # --- execution --------------------------------------------------------
    COMMAND_TIMEOUT_SECONDS: int = 1200
    MAX_RETRIES_DEFAULT: int = 2
    WORKER_POLL_SECONDS: float = 2.0
    WORKER_ID: str = "worker-1"
    WORKER_LOCK_STALE_MINUTES: int = 90
    KEEP_TASK_WORKSPACES: bool = True
    GIT_AUTHOR_NAME: str = "H-Caliper"
    GIT_AUTHOR_EMAIL: str = "factory@hcaliper.local"

    # --- deployment -------------------------------------------------------
    ALLOW_PRODUCTION_DEPLOYMENT: bool = False
    DEPLOYMENT_COMMAND_ALLOWLIST: Annotated[List[str], NoDecode] = []

    # --- bootstrap --------------------------------------------------------
    # Optional first-run administrator. Never a default password: if the email
    # is set, a random password is generated and printed once at startup.
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    AUDIT_RETENTION_DAYS: int = 365

    @field_validator("CORS_ORIGINS", "ALLOWED_LOCAL_REPO_ROOTS", "DEPLOYMENT_COMMAND_ALLOWLIST", mode="before")
    @classmethod
    def _split_csv(cls, value):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_db_url(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://"):]
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://"):]
        return value

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def validate_runtime_secrets() -> None:
    """Fail closed when production starts with development credentials."""
    if not settings.is_production:
        if settings.SECRET_KEY.startswith("dev-only"):
            logger.warning("Using the development SECRET_KEY; do not use in production")
        return
    problems = []
    if settings.SECRET_KEY.startswith("dev-only") or len(settings.SECRET_KEY) < 32:
        problems.append("SECRET_KEY must be a random value of at least 32 characters")
    if not settings.ENCRYPTION_KEY:
        problems.append("ENCRYPTION_KEY must be configured")
    if not settings.COOKIE_SECURE:
        problems.append("COOKIE_SECURE must be true in production")
    if problems:
        raise RuntimeError("Invalid production configuration: " + "; ".join(problems))
