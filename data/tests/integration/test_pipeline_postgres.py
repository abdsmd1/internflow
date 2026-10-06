"""Bout en bout : PostgreSQL migré → seed → bronze → silver → gold, via la ligne de commande.

Nécessite une base de test (`INTERNFLOW_TEST_DATABASE_URL`) et le pilote JDBC
(`INTERNFLOW_DATA_JDBC_DRIVER_JAR`) ; sinon le module est ignoré.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from pyspark.sql import DataFrame, SparkSession
from sqlalchemy import Engine, create_engine, make_url, text

from internflow_data import __main__ as cli
from internflow_data.quality import DataQualityError

pytestmark = pytest.mark.integration

API_ROOT = Path(__file__).resolve().parents[3] / "services" / "api"
TODAY = "2026-10-06"
SALT = "sel-integration-0123456789"
TABLES = "weekly_reports, tasks, users, internships, supervisors, interns"
PII_COLUMNS = {
    "first_name",
    "last_name",
    "email",
    "subject",
    "title",
    "description",
    "accomplishments",
    "difficulties",
    "next_steps",
    "feedback",
    "password_hash",
}


def to_jdbc(sqlalchemy_url: str) -> tuple[str, str, str]:
    """`postgresql+psycopg://u:p@h:port/db` → (`jdbc:postgresql://h:port/db`, u, p)."""
    url = make_url(sqlalchemy_url)
    port = url.port or 5432
    return (
        f"jdbc:postgresql://{url.host}:{port}/{url.database}",
        url.username or "",
        url.password or "",
    )


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("INTERNFLOW_TEST_DATABASE_URL")
    jar = os.environ.get("INTERNFLOW_DATA_JDBC_DRIVER_JAR")
    if not url or not jar:
        pytest.skip("INTERNFLOW_TEST_DATABASE_URL ou INTERNFLOW_DATA_JDBC_DRIVER_JAR absent.")
    return url


@pytest.fixture(scope="module")
def engine(database_url: str) -> Iterator[Engine]:
    alembic_cfg = Config(str(API_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")
    db_engine = create_engine(database_url)
    with db_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES}"))
    yield db_engine
    with db_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {TABLES}"))
    db_engine.dispose()


@pytest.fixture
def environment(
    database_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spark: SparkSession
) -> Path:
    jdbc_url, user, password = to_jdbc(database_url)
    lake = tmp_path / "lake"
    for name, value in {
        "INTERNFLOW_DATABASE_URL": database_url,
        "INTERNFLOW_DATA_JDBC_URL": jdbc_url,
        "INTERNFLOW_DATA_JDBC_USER": user,
        "INTERNFLOW_DATA_JDBC_PASSWORD": password,
        "INTERNFLOW_DATA_LAKE_PATH": str(lake),
        "INTERNFLOW_DATA_PSEUDONYMIZATION_SALT": SALT,
    }.items():
        monkeypatch.setenv(name, value)
    # La CLI arrête sa session Spark ; ici elle réutilise celle des tests, qu'il faut garder.
    monkeypatch.setattr(spark, "stop", lambda: None)
    return lake


def read(spark: SparkSession, lake: Path, layer: str, dataset: str) -> DataFrame:
    return spark.read.parquet(str(lake / layer / dataset))


def test_full_pipeline(
    engine: Engine, environment: Path, spark: SparkSession, capsys: pytest.CaptureFixture[str]
) -> None:
    lake = environment
    seed_args = ["seed", "--supervisors", "5", "--interns", "40", "--seed", "3", "--date", TODAY]
    assert cli.main(seed_args) == 0
    assert cli.main(seed_args) == 1  # mêmes données : refus propre, pas de doublons

    assert cli.main(["pipeline", "--date", TODAY]) == 0

    with engine.connect() as connection:
        measured = connection.scalar(
            text("SELECT count(*) FROM internships WHERE status IN ('ongoing', 'completed')")
        )
        raw_ids = set(connection.scalars(text("SELECT id::text FROM interns")))
        task_count = connection.scalar(text("SELECT count(*) FROM tasks"))

    kpis = read(spark, lake, "gold", "internship_kpis")
    assert kpis.count() == measured
    assert read(spark, lake, "silver", "tasks").count() == task_count

    # Minimisation : aucune colonne personnelle, aucun identifiant brut dans silver et gold.
    for layer, dataset in [
        ("silver", "interns"),
        ("silver", "supervisors"),
        ("silver", "internships"),
        ("silver", "weekly_reports"),
        ("gold", "internship_kpis"),
        ("gold", "supervisor_workload"),
    ]:
        df = read(spark, lake, layer, dataset)
        assert not PII_COLUMNS & set(df.columns)
        values = {str(v) for row in df.collect() for v in row}
        assert not raw_ids & values

    # Idempotence : relancer le même jour ne duplique rien.
    assert cli.main(["pipeline", "--date", TODAY]) == 0
    assert read(spark, lake, "gold", "internship_kpis").count() == measured
    assert read(spark, lake, "bronze", "tasks").count() == task_count

    # Aperçu lisible d'un indicateur, puis cas d'une date jamais calculée.
    capsys.readouterr()
    assert cli.main(["show", "supervisor_workload", "--date", TODAY]) == 0
    assert "supervisor_workload au 2026-10-06 : 5 lignes" in capsys.readouterr().out
    assert cli.main(["show", "weekly_activity", "--date", "2020-01-01"]) == 1


def test_quality_failure_exits_with_code_2(
    environment: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_: object) -> dict[str, int]:
        raise DataQualityError("gold.test", [])

    monkeypatch.setattr(cli, "aggregate", broken)
    assert cli.main(["pipeline", "--step", "aggregate", "--date", TODAY]) == 2


def test_to_jdbc() -> None:
    assert to_jdbc("postgresql+psycopg://u:p@db:5433/x") == (
        "jdbc:postgresql://db:5433/x",
        "u",
        "p",
    )
    assert to_jdbc("postgresql+psycopg://u@db/x")[0] == "jdbc:postgresql://db:5432/x"
