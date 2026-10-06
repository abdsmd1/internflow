"""Bronze → silver : typage, nettoyage, dédoublonnage et pseudonymisation.

Pseudonymisation : chaque identifiant est remplacé par SHA-256(sel ‖ identifiant).
Sans le sel (secret), impossible de relier les données analytiques à une personne
de la base applicative ; avec le même sel, les jointures restent possibles.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from internflow_data.schemas import SourceTable


def conform(df: DataFrame, source: SourceTable) -> DataFrame:
    """Impose le contrat de la table : colonnes attendues, dans l'ordre, au bon type.

    Une colonne manquante fait échouer le job immédiatement (plutôt qu'un indicateur faux).
    """
    missing = set(source.schema.fieldNames()) - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes dans « {source.name} » : {sorted(missing)}.")
    return df.select(
        *(F.col(field.name).cast(field.dataType).alias(field.name) for field in source.schema)
    )


def pseudonymize(column: str, salt: str) -> Column:
    return F.sha2(F.concat(F.lit(salt), F.col(column)), 256)


def latest_per_id(df: DataFrame, order_by: str = "created_at") -> DataFrame:
    """Une seule ligne par identifiant (la plus récente) : protège des doublons d'extraction."""
    window = Window.partitionBy("id").orderBy(F.col(order_by).desc())
    return df.withColumn("_rank", F.row_number().over(window)).filter("_rank = 1").drop("_rank")


def monday_of(date_column: Column) -> Column:
    """Lundi de la semaine ISO contenant la date (Spark : weekday() = 0 le lundi)."""
    return F.date_sub(date_column, F.weekday(date_column))


def iso_week_start(iso_year: Column, iso_week: Column) -> Column:
    """Lundi de la semaine ISO `iso_year-Wiso_week`.

    Le 4 janvier appartient toujours à la semaine 1 : on part du lundi de cette
    semaine-là, puis on avance de 7 * (semaine - 1) jours.
    """
    january_4th = F.make_date(iso_year.cast("int"), F.lit(1), F.lit(4))
    # date_add exige un INT : sans cast, une colonne BIGINT ferait échouer l'analyse.
    return F.date_add(monday_of(january_4th), ((iso_week - 1) * 7).cast("int"))


def refine_interns(df: DataFrame, salt: str) -> DataFrame:
    return latest_per_id(df).select(
        pseudonymize("id", salt).alias("intern_key"),
        F.trim("school").alias("school"),
        F.col("study_level"),
    )


def refine_supervisors(df: DataFrame, salt: str) -> DataFrame:
    return latest_per_id(df).select(
        pseudonymize("id", salt).alias("supervisor_key"),
        F.trim("department").alias("department"),
        F.col("max_interns"),
    )


def refine_internships(df: DataFrame, salt: str) -> DataFrame:
    return latest_per_id(df).select(
        pseudonymize("id", salt).alias("internship_key"),
        pseudonymize("intern_id", salt).alias("intern_key"),
        pseudonymize("supervisor_id", salt).alias("supervisor_key"),
        F.col("status"),
        F.col("start_date"),
        F.col("end_date"),
        (F.datediff("end_date", "start_date") + 1).alias("duration_days"),
    )


def refine_tasks(df: DataFrame, salt: str) -> DataFrame:
    completed_date = F.to_date("completed_at")
    return latest_per_id(df).select(
        pseudonymize("id", salt).alias("task_key"),
        pseudonymize("internship_id", salt).alias("internship_key"),
        F.col("status"),
        F.col("due_date"),
        F.to_date("created_at").alias("created_date"),
        completed_date.alias("completed_date"),
        # > 0 : terminée en retard ; ≤ 0 : à l'heure. Nul tant que non terminée.
        F.datediff(completed_date, F.col("due_date")).alias("delay_days"),
    )


def refine_reports(df: DataFrame, salt: str) -> DataFrame:
    week_start = iso_week_start(F.col("iso_year"), F.col("iso_week"))
    return latest_per_id(df, order_by="submitted_at").select(
        pseudonymize("id", salt).alias("report_key"),
        pseudonymize("internship_id", salt).alias("internship_key"),
        F.col("iso_year"),
        F.col("iso_week"),
        week_start.alias("week_start"),
        F.col("status"),
        F.to_date("submitted_at").alias("submitted_date"),
        F.datediff(F.to_date("reviewed_at"), F.to_date("submitted_at")).alias("review_lag_days"),
    )
