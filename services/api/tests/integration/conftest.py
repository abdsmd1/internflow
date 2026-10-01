"""Fixtures d'intégration : une vraie base PostgreSQL migrée par Alembic."""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from internflow_api.infrastructure.persistence.sqlalchemy_uow import build_engine

API_ROOT = Path(__file__).resolve().parents[2]


def _docker_available() -> bool:
    """Vérifie qu'un démon Docker répond, sans laisser de ressource ouverte."""
    if os.environ.get("DOCKER_HOST"):
        return True
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        try:
            sock.connect("/var/run/docker.sock")
        except OSError:
            return False
    return True


def _migrate(url: str) -> None:
    """Applique les migrations, les annule puis les réapplique.

    Ce « test de l'escalier » garantit que chaque migration est réversible.
    """
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    # 1) Base fournie explicitement (CI avec service PostgreSQL, poste local…)
    if url := os.environ.get("INTERNFLOW_TEST_DATABASE_URL"):
        yield url
        return
    # 2) Sinon, un PostgreSQL jetable via Testcontainers
    if not _docker_available():
        pytest.skip("Ni Docker ni INTERNFLOW_TEST_DATABASE_URL : tests d'intégration ignorés.")
    from testcontainers.postgres import PostgresContainer  # noqa: PLC0415

    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="module")
def engine(database_url: str) -> Iterator[Engine]:
    _migrate(database_url)
    db_engine = build_engine(database_url)
    yield db_engine
    db_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(engine: Engine) -> Iterator[None]:
    yield
    with engine.begin() as connection:  # isolation entre tests
        connection.execute(text("TRUNCATE interns"))
