"""Contrats de données : ce que la couche bronze extrait de PostgreSQL, et avec quels types.

Minimisation des données (RGPD / loi 09-08) : on n'extrait **que** les colonnes
utiles aux indicateurs. Les noms, e-mails, mots de passe et textes libres des
rapports ne quittent jamais la base applicative.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql.types import (
    DateType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


def _schema(*fields: tuple[str, object, bool]) -> StructType:
    return StructType([StructField(name, kind, nullable) for name, kind, nullable in fields])  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SourceTable:
    name: str
    query: str
    schema: StructType


SOURCE_TABLES: tuple[SourceTable, ...] = (
    SourceTable(
        "interns",
        "SELECT id::text AS id, school, study_level, created_at FROM interns",
        _schema(
            ("id", StringType(), False),
            ("school", StringType(), False),
            ("study_level", StringType(), False),
            ("created_at", TimestampType(), False),
        ),
    ),
    SourceTable(
        "supervisors",
        "SELECT id::text AS id, department, max_interns, created_at FROM supervisors",
        _schema(
            ("id", StringType(), False),
            ("department", StringType(), False),
            ("max_interns", IntegerType(), False),
            ("created_at", TimestampType(), False),
        ),
    ),
    SourceTable(
        "internships",
        "SELECT id::text AS id, intern_id::text AS intern_id, supervisor_id::text AS supervisor_id,"
        " status, start_date, end_date, created_at FROM internships",
        _schema(
            ("id", StringType(), False),
            ("intern_id", StringType(), False),
            ("supervisor_id", StringType(), False),
            ("status", StringType(), False),
            ("start_date", DateType(), False),
            ("end_date", DateType(), False),
            ("created_at", TimestampType(), False),
        ),
    ),
    SourceTable(
        "tasks",
        "SELECT id::text AS id, internship_id::text AS internship_id, due_date, status,"
        " created_at, completed_at FROM tasks",
        _schema(
            ("id", StringType(), False),
            ("internship_id", StringType(), False),
            ("due_date", DateType(), False),
            ("status", StringType(), False),
            ("created_at", TimestampType(), False),
            ("completed_at", TimestampType(), True),
        ),
    ),
    SourceTable(
        "weekly_reports",
        "SELECT id::text AS id, internship_id::text AS internship_id, iso_year, iso_week,"
        " status, submitted_at, reviewed_at FROM weekly_reports",
        _schema(
            ("id", StringType(), False),
            ("internship_id", StringType(), False),
            ("iso_year", IntegerType(), False),
            ("iso_week", IntegerType(), False),
            ("status", StringType(), False),
            ("submitted_at", TimestampType(), False),
            ("reviewed_at", TimestampType(), True),
        ),
    ),
)

SOURCE_BY_NAME = {table.name: table for table in SOURCE_TABLES}
