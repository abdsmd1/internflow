"""PostgreSQL → bronze (JDBC)."""

from __future__ import annotations

from datetime import date

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from internflow_data.config import DataSettings
from internflow_data.schemas import SOURCE_TABLES
from internflow_data.transformations.silver import conform


def bronze_path(settings: DataSettings, table: str) -> str:
    return str(settings.lake_path / "bronze" / table)


def extract(spark: SparkSession, settings: DataSettings, run_date: date) -> dict[str, int]:
    """Copie chaque table source dans la partition `ingestion_date=run_date`."""
    counts: dict[str, int] = {}
    for source in SOURCE_TABLES:
        raw = (
            spark.read.format("jdbc")
            .option("url", settings.jdbc_url)
            .option("query", source.query)  # SELECT explicite : minimisation des données
            .option("user", settings.jdbc_user)
            .option("password", settings.jdbc_password.get_secret_value())
            .option("driver", "org.postgresql.Driver")
            .option("fetchsize", 1000)
            .load()
        )
        bronze = conform(raw, source).withColumn("ingestion_date", F.lit(run_date))
        bronze.write.mode("overwrite").partitionBy("ingestion_date").parquet(
            bronze_path(settings, source.name)
        )
        counts[source.name] = bronze.count()
    return counts
