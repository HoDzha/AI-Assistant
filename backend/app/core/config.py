from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
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
    allowed_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ]
    )

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_request_timeout_seconds: float = 30.0
    openai_max_attempts: int = 3
    openai_retry_base_delay_seconds: float = 1.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
