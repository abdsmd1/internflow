"""Création de la session Spark, configurée une seule fois et de façon explicite."""

from __future__ import annotations

from pathlib import Path

from pyspark.sql import SparkSession


def build_spark_session(
    app_name: str, *, master: str = "local[*]", jars: list[Path] | None = None
) -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        # Toutes les dates/heures sont interprétées en UTC, comme dans l'API.
        .config("spark.sql.session.timeZone", "UTC")
        # Réécrire une partition ne supprime que cette partition : jobs idempotents.
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")
        # Petits volumes : peu de partitions de shuffle (200 par défaut).
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.ui.enabled", "false")
    )
    if jars:
        builder = builder.config("spark.jars", ",".join(str(j) for j in jars))
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")
    return spark
