"""Configuration centralisée, lue depuis l'environnement (12-Factor, facteur III)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERNFLOW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    environment: Environment = Environment.LOCAL
    log_level: str = "INFO"
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://internflow:change-me@localhost:5432/internflow"),
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)
    cors_origins: list[str] = Field(default_factory=list)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def docs_enabled(self) -> bool:
        # La documentation interactive n'est pas exposée en production.
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()
