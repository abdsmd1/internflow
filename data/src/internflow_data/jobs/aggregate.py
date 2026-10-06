"""Silver → gold : indicateurs, un instantané par date `as_of`."""

from __future__ import annotations

from datetime import date

from pyspark.sql import DataFrame, SparkSession

from internflow_data import quality as q
from internflow_data.config import DataSettings
from internflow_data.jobs.refine import silver_path
from internflow_data.transformations import gold


def gold_path(settings: DataSettings, indicator: str) -> str:
    return str(settings.lake_path / "gold" / indicator)


def _publish(df: DataFrame, settings: DataSettings, indicator: str) -> int:
    df.write.mode("overwrite").partitionBy("as_of").parquet(gold_path(settings, indicator))
    return df.count()


def aggregate(spark: SparkSession, settings: DataSettings, as_of: date) -> dict[str, int]:
    def read(dataset: str) -> DataFrame:
        return spark.read.parquet(silver_path(settings, dataset))

    internships, supervisors = read("internships"), read("supervisors")
    tasks, reports = read("tasks"), read("weekly_reports")

    kpis = gold.internship_kpis(internships, supervisors, tasks, reports, as_of).cache()
    q.enforce(
        "gold.internship_kpis",
        [
            q.expect_unique(kpis, "internship_key"),
            q.expect_between(kpis, "on_time_rate", 0, 1),
            q.expect_between(kpis, "report_regularity", 0, 1),
            q.expect_between(kpis, "overdue_open_tasks", 0, 10_000),
        ],
    )
    workload = gold.supervisor_workload(internships, supervisors, reports, as_of).cache()
    q.enforce(
        "gold.supervisor_workload",
        [
            q.expect_unique(workload, "supervisor_key"),
            # Règle métier vérifiée a posteriori : aucun encadrant au-delà de sa capacité.
            q.expect_between(workload, "utilization", 0, 1),
        ],
    )
    activity = gold.weekly_activity(tasks, reports, as_of)

    return {
        "internship_kpis": _publish(kpis, settings, "internship_kpis"),
        "supervisor_workload": _publish(workload, settings, "supervisor_workload"),
        "weekly_activity": _publish(activity, settings, "weekly_activity"),
    }
