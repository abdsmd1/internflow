"""Fixtures partagées : une session Spark locale, créée une seule fois pour tous les tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pyspark.sql import SparkSession

from internflow_data.spark import build_spark_session


@pytest.fixture(scope="session")
def spark() -> Iterator[SparkSession]:
    # Le pilote JDBC n'est utile qu'aux tests d'intégration (lecture de PostgreSQL).
    jar = os.environ.get("INTERNFLOW_DATA_JDBC_DRIVER_JAR")
    session = build_spark_session(
        "internflow-tests", master="local[1]", jars=[Path(jar)] if jar else None
    )
    yield session
    session.stop()
