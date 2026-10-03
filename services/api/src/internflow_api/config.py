"""Configuration centralisée, lue depuis l'environnement (12-Factor, facteur III).

Deux niveaux, selon le principe du moindre privilège :
- `DatabaseSettings` : juste ce qu'il faut pour les migrations et la ligne de commande ;
- `Settings` : la configuration complète de l'API (dont le secret de signature JWT).
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_MODEL_CONFIG = SettingsConfigDict(
    env_prefix="INTERNFLOW_",
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    frozen=True,
)


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseSettings(BaseSettings):
    model_config = _MODEL_CONFIG

    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://internflow:change-me@localhost:5432/internflow"),
    )
    database_pool_size: int = Field(default=5, ge=1, le=50)


class Settings(DatabaseSettings):
    model_config = _MODEL_CONFIG

    environment: Environment = Environment.LOCAL
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)

    # Aucun défaut : l'API refuse de démarrer sans secret (pas de secret faible oublié).
    jwt_secret: SecretStr = Field(min_length=32)
    access_token_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def docs_enabled(self) -> bool:
        # La documentation interactive n'est pas exposée en production.
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()  # les valeurs obligatoires sont lues dans l'environnement
