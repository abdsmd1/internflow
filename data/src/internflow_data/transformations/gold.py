"""Silver → gold : indicateurs prêts à l'emploi (tableaux de bord, agent IA).

Tous les indicateurs sont calculés « à la date du » `as_of`, passée en paramètre :
le même calcul, rejoué pour la même date, donne exactement le même résultat.
"""

from __future__ import annotations

from datetime import date

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from internflow_data.transformations.silver import monday_of

# Stages qui ont une activité à mesurer (les stages prévus ou annulés sont exclus).
MEASURED_STATUSES = ("ongoing", "completed")


def _ratio(numerator: Column, denominator: Column) -> Column:
    return F.when(denominator > 0, F.round(numerator / denominator, 4))


def expected_reports(start: Column, end: Column, as_of: date) -> Column:
    """Nombre de rapports attendus : une semaine ISO terminée = un rapport.

    On compte de la semaine de début jusqu'à la dernière semaine **terminée**
    (la semaine en cours n'est pas encore due), sans dépasser la fin du stage.
    """
    last_day = F.least(end, F.date_sub(F.lit(as_of), 7))
    weeks = F.floor(F.datediff(monday_of(last_day), monday_of(start)) / 7) + 1
    return F.when(last_day < start, F.lit(0)).otherwise(weeks).cast("int")


def internship_kpis(
    internships: DataFrame,
    supervisors: DataFrame,
    tasks: DataFrame,
    reports: DataFrame,
    as_of: date,
) -> DataFrame:
    today = F.lit(as_of)
    task_stats = tasks.groupBy("internship_key").agg(
        F.count("*").alias("tasks_total"),
        F.sum(F.when(F.col("status") == "done", 1).otherwise(0)).alias("tasks_done"),
        F.sum(
            F.when((F.col("status") == "done") & (F.col("delay_days") <= 0), 1).otherwise(0)
        ).alias("tasks_done_on_time"),
        F.sum(
            F.when((F.col("status") != "done") & (F.col("due_date") < today), 1).otherwise(0)
        ).alias("overdue_open_tasks"),
        F.round(F.avg("delay_days"), 2).alias("avg_delay_days"),
    )
    report_stats = reports.groupBy("internship_key").agg(
        F.count("*").alias("reports_submitted"),
        F.sum(F.when(F.col("status") == "reviewed", 1).otherwise(0)).alias("reports_reviewed"),
        F.round(F.avg("review_lag_days"), 2).alias("avg_review_lag_days"),
    )
    zero_if_missing = [
        "tasks_total",
        "tasks_done",
        "tasks_done_on_time",
        "overdue_open_tasks",
        "reports_submitted",
        "reports_reviewed",
    ]
    return (
        internships.filter(F.col("status").isin(*MEASURED_STATUSES))
        .join(supervisors.select("supervisor_key", "department"), "supervisor_key", "left")
        .join(task_stats, "internship_key", "left")
        .join(report_stats, "internship_key", "left")
        .fillna(0, subset=zero_if_missing)
        .withColumn(
            "reports_expected", expected_reports(F.col("start_date"), F.col("end_date"), as_of)
        )
        .select(
            "internship_key",
            "intern_key",
            "supervisor_key",
            "department",
            "status",
            "start_date",
            "end_date",
            "tasks_total",
            "tasks_done",
            "tasks_done_on_time",
            _ratio(F.col("tasks_done_on_time"), F.col("tasks_done")).alias("on_time_rate"),
            "overdue_open_tasks",
            "avg_delay_days",
            "reports_expected",
            "reports_submitted",
            # `least` ignore les nuls : on garde explicitement NULL quand rien n'est attendu.
            F.when(
                F.col("reports_expected") > 0,
                F.least(F.lit(1.0), _ratio(F.col("reports_submitted"), F.col("reports_expected"))),
            ).alias("report_regularity"),
            "reports_reviewed",
            "avg_review_lag_days",
            today.alias("as_of"),
        )
    )


def supervisor_workload(
    internships: DataFrame, supervisors: DataFrame, reports: DataFrame, as_of: date
) -> DataFrame:
    active = (
        internships.filter(F.col("status") == "ongoing")
        .groupBy("supervisor_key")
        .agg(F.count("*").alias("active_internships"))
    )
    review_stats = (
        reports.join(internships.select("internship_key", "supervisor_key"), "internship_key")
        .groupBy("supervisor_key")
        .agg(
            F.sum(F.when(F.col("status") == "submitted", 1).otherwise(0)).alias("pending_reviews"),
            F.round(F.avg("review_lag_days"), 2).alias("avg_review_lag_days"),
        )
    )
    return (
        supervisors.join(active, "supervisor_key", "left")
        .join(review_stats, "supervisor_key", "left")
        .fillna(0, subset=["active_internships", "pending_reviews"])
        .select(
            "supervisor_key",
            "department",
            "max_interns",
            "active_internships",
            _ratio(F.col("active_internships"), F.col("max_interns")).alias("utilization"),
            "pending_reviews",
            "avg_review_lag_days",
            F.lit(as_of).alias("as_of"),
        )
    )


def _iso_year_week(day: Column) -> tuple[Column, Column]:
    """Année et numéro de semaine ISO d'une date (l'année ISO est celle du jeudi)."""
    return F.year(F.date_add(monday_of(day), 3)), F.weekofyear(day)


def weekly_activity(tasks: DataFrame, reports: DataFrame, as_of: date) -> DataFrame:
    completed_year, completed_week = _iso_year_week(F.col("completed_date"))
    tasks_per_week = (
        tasks.filter(F.col("completed_date").isNotNull())
        .groupBy(completed_year.alias("iso_year"), completed_week.alias("iso_week"))
        .agg(F.count("*").alias("tasks_completed"))
    )
    reports_per_week = reports.groupBy("iso_year", "iso_week").agg(
        F.count("*").alias("reports_submitted")
    )
    return (
        reports_per_week.join(tasks_per_week, ["iso_year", "iso_week"], "full_outer")
        .fillna(0, subset=["reports_submitted", "tasks_completed"])
        .withColumn("as_of", F.lit(as_of))
        .orderBy("iso_year", "iso_week")
    )
