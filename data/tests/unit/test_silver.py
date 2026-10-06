from datetime import UTC, date, datetime

import pytest
from pyspark.sql import Row, SparkSession
from pyspark.sql import functions as F

from internflow_data.schemas import SOURCE_BY_NAME
from internflow_data.transformations import silver

SALT = "sel-de-test-0123456789"
CREATED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


class TestConform:
    def test_keeps_only_contract_columns_with_their_types(self, spark: SparkSession) -> None:
        raw = spark.createDataFrame(
            [("s1", "IA", "5", CREATED, "colonne en trop")],
            ["id", "department", "max_interns", "created_at", "extra"],
        )
        conformed = silver.conform(raw, SOURCE_BY_NAME["supervisors"])
        assert conformed.columns == ["id", "department", "max_interns", "created_at"]
        assert dict(conformed.dtypes)["max_interns"] == "int"

    def test_missing_column_fails_fast(self, spark: SparkSession) -> None:
        raw = spark.createDataFrame([("s1", "IA")], ["id", "department"])
        with pytest.raises(ValueError, match="max_interns"):
            silver.conform(raw, SOURCE_BY_NAME["supervisors"])


class TestPseudonymization:
    def test_same_id_and_salt_give_the_same_key(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("abc",), ("abc",), ("xyz",)], ["id"])
        keys = [r.k for r in df.select(silver.pseudonymize("id", SALT).alias("k")).collect()]
        assert keys[0] == keys[1] != keys[2]
        assert len(keys[0]) == 64  # SHA-256 en hexadécimal

    def test_another_salt_gives_unlinkable_keys(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([("abc",)], ["id"])
        first = df.select(silver.pseudonymize("id", SALT)).first()
        second = df.select(silver.pseudonymize("id", "un-autre-sel-secret")).first()
        assert first != second

    def test_identifiers_never_reach_silver(self, spark: SparkSession) -> None:
        raw = spark.createDataFrame(
            [
                (
                    "internship-1",
                    "intern-1",
                    "sup-1",
                    "ongoing",
                    date(2026, 10, 1),
                    date(2027, 1, 31),
                    CREATED,
                )
            ],
            SOURCE_BY_NAME["internships"].schema,
        )
        refined = silver.refine_internships(raw, SALT)
        values = {str(v) for row in refined.collect() for v in row}
        assert not {"internship-1", "intern-1", "sup-1"} & values


class TestRefineTasks:
    def test_delay_is_positive_when_late_and_null_when_open(self, spark: SparkSession) -> None:
        raw = spark.createDataFrame(
            [
                (
                    "t1",
                    "i1",
                    date(2026, 10, 15),
                    "done",
                    CREATED,
                    datetime(2026, 10, 18, 17, tzinfo=UTC),
                ),
                (
                    "t2",
                    "i1",
                    date(2026, 10, 15),
                    "done",
                    CREATED,
                    datetime(2026, 10, 14, 17, tzinfo=UTC),
                ),
                ("t3", "i1", date(2026, 10, 15), "todo", CREATED, None),
            ],
            SOURCE_BY_NAME["tasks"].schema,
        )
        delays = [
            r.delay_days
            for r in silver.refine_tasks(raw, SALT)
            .orderBy("due_date", F.col("delay_days").desc_nulls_last())
            .collect()
        ]
        assert sorted(delays, key=lambda d: (d is None, d)) == [-1, 3, None]

    def test_duplicates_keep_the_latest_version(self, spark: SparkSession) -> None:
        later = datetime(2026, 10, 2, tzinfo=UTC)
        raw = spark.createDataFrame(
            [
                ("t1", "i1", date(2026, 10, 15), "todo", CREATED, None),
                ("t1", "i1", date(2026, 10, 15), "in_progress", later, None),
            ],
            SOURCE_BY_NAME["tasks"].schema,
        )
        [row] = silver.refine_tasks(raw, SALT).collect()
        assert row.status == "in_progress"


class TestIsoWeeks:
    @pytest.mark.parametrize(
        ("iso_year", "iso_week", "monday"),
        [
            (2026, 41, date(2026, 10, 5)),
            (2026, 1, date(2025, 12, 29)),  # la semaine 1 de 2026 commence en 2025
            (2026, 53, date(2026, 12, 28)),
            (2027, 1, date(2027, 1, 4)),
        ],
    )
    def test_iso_week_start(
        self, spark: SparkSession, iso_year: int, iso_week: int, monday: date
    ) -> None:
        df = spark.createDataFrame([Row(y=iso_year, w=iso_week)])
        [row] = df.select(silver.iso_week_start(F.col("y"), F.col("w")).alias("d")).collect()
        assert row.d == monday

    def test_monday_of(self, spark: SparkSession) -> None:
        df = spark.createDataFrame([Row(d=date(2026, 10, 11))])  # un dimanche
        assert df.select(silver.monday_of(F.col("d")).alias("m")).first().m == date(2026, 10, 5)  # type: ignore[union-attr]

    def test_review_lag(self, spark: SparkSession) -> None:
        raw = spark.createDataFrame(
            [
                (
                    "r1",
                    "i1",
                    2026,
                    41,
                    "reviewed",
                    datetime(2026, 10, 9, 17, tzinfo=UTC),
                    datetime(2026, 10, 12, 8, tzinfo=UTC),
                )
            ],
            SOURCE_BY_NAME["weekly_reports"].schema,
        )
        [row] = silver.refine_reports(raw, SALT).collect()
        assert (row.week_start, row.review_lag_days) == (date(2026, 10, 5), 3)
