from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Freelance Task AI Manager"
    app_version: str = "1.0.0"
    api_prefix: str = "/api"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    database_url: str = "sqlite:///./data/freelance_flow.db"
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ]
    )

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_request_timeout_seconds: float = 30.0
    openai_max_attempts: int = 3
    openai_retry_base_delay_seconds: float = 1.0
    openai_cache_ttl_seconds: int = 900
    openai_cache_max_entries: int = 128

    @field_validator("openai_base_url")
    @classmethod
    def validate_openai_base_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("http://", "https://")):
            raise ValueError("openai_base_url must start with http:// or https://")
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        scheme, separator, remainder = value.partition(":///")
        if not separator or not scheme:
            raise ValueError("database_url must use the format engine:///path")

        if not remainder:
            raise ValueError("database_url must include a database path")

        if scheme == "sqlite" and remainder != ":memory:":
            path = Path(remainder)
            if path.name in {"", ".", ".."}:
                raise ValueError("database_url must point to a database file")

        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
