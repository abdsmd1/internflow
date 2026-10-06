"""Configuration des traitements de données (12-Factor : tout vient de l'environnement)."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERNFLOW_DATA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # Source : PostgreSQL de l'application, lu en JDBC par Spark.
    jdbc_url: str = "jdbc:postgresql://localhost:5432/internflow"
    jdbc_user: str = "internflow"
    jdbc_password: SecretStr = SecretStr("")
    jdbc_driver_jar: Path = Path("/opt/jars/postgresql.jar")

    # Destination : le « data lake » (dossier local, MinIO / S3 plus tard).
    lake_path: Path = Path("lake")

    # Sel de pseudonymisation : sans lui, impossible de relier les données
    # analytiques aux personnes. Aucun défaut : il doit être fourni.
    pseudonymization_salt: SecretStr = Field(min_length=16)

    spark_master: str = "local[*]"
