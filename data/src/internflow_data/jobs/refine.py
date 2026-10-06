"""Bronze → silver, avec contrôles de qualité."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from internflow_data import quality as q
from internflow_data.config import DataSettings
from internflow_data.jobs.extract import bronze_path
from internflow_data.transformations import silver

INTERNSHIP_STATUSES = ("planned", "ongoing", "completed", "cancelled")
TASK_STATUSES = ("todo", "in_progress", "done")
REPORT_STATUSES = ("submitted", "reviewed")


def silver_path(settings: DataSettings, dataset: str) -> str:
    return str(settings.lake_path / "silver" / dataset)


def _checks(dataset: str, df: DataFrame) -> list[q.CheckResult | list[q.CheckResult]]:
    match dataset:
        case "interns":
            return [q.expect_not_null(df, "intern_key"), q.expect_unique(df, "intern_key")]
        case "supervisors":
            return [
                q.expect_not_null(df, "supervisor_key"),
                q.expect_unique(df, "supervisor_key"),
                q.expect_between(df, "max_interns", 1, 10),
            ]
        case "internships":
            return [
                q.expect_not_null(df, "internship_key", "intern_key", "supervisor_key"),
                q.expect_unique(df, "internship_key"),
                q.expect_in(df, "status", INTERNSHIP_STATUSES),
                q.expect_between(df, "duration_days", 1, 183),
            ]
        case "tasks":
            return [
                q.expect_unique(df, "task_key"),
                q.expect_in(df, "status", TASK_STATUSES),
                q.expect(
                    df,
                    "terminée ⇔ date de réalisation",
                    (F.col("status") == "done") == F.col("completed_date").isNotNull(),
                ),
            ]
        case "weekly_reports":
            return [
                q.expect_unique(df, "report_key"),
                q.expect_unique(df, "internship_key", "iso_year", "iso_week"),
                q.expect_between(df, "iso_week", 1, 53),
                q.expect_in(df, "status", REPORT_STATUSES),
            ]
    raise ValueError(f"Jeu de données inconnu : {dataset}")


REFINERS: dict[str, Callable[[DataFrame, str], DataFrame]] = {
    "interns": silver.refine_interns,
    "supervisors": silver.refine_supervisors,
    "internships": silver.refine_internships,
    "tasks": silver.refine_tasks,
    "weekly_reports": silver.refine_reports,
}


def refine(spark: SparkSession, settings: DataSettings, run_date: date) -> dict[str, int]:
    salt = settings.pseudonymization_salt.get_secret_value()
    counts: dict[str, int] = {}
    for dataset, refiner in REFINERS.items():
        bronze = spark.read.parquet(bronze_path(settings, dataset)).filter(
            F.col("ingestion_date") == F.lit(run_date)
        )
        refined = refiner(bronze, salt).cache()
        q.enforce(f"silver.{dataset}", _checks(dataset, refined))
        refined.write.mode("overwrite").parquet(silver_path(settings, dataset))
        counts[dataset] = refined.count()
        refined.unpersist()
    return counts
