import pytest
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from internflow_data import quality as q


def test_checks_count_failing_rows(spark: SparkSession) -> None:
    df = spark.createDataFrame(
        [("a", "done", 0.5), ("a", "lost", 1.5), (None, "todo", None)],
        "k string, s string, r double",
    )
    assert q.expect_unique(df, "k").failing_rows == 1
    assert [c.failing_rows for c in q.expect_not_null(df, "k", "s")] == [1, 0]
    assert q.expect_in(df, "s", ["todo", "done"]).failing_rows == 1
    assert q.expect_between(df, "r", 0, 1).failing_rows == 1  # les nuls sont tolérés
    assert q.expect(df, "taux renseigné", F.col("r").isNotNull()).failing_rows == 1


def test_enforce_lists_every_failure(spark: SparkSession) -> None:
    df = spark.createDataFrame([("a",), ("a",)], "k string")
    with pytest.raises(q.DataQualityError, match="unicité de \\(k\\) \\(1 ligne") as error:
        q.enforce("silver.test", [q.expect_unique(df, "k"), q.expect_not_null(df, "k")])
    assert [f.name for f in error.value.failures] == ["unicité de (k)"]


def test_enforce_passes_silently_on_clean_data(spark: SparkSession) -> None:
    df = spark.createDataFrame([("a",), ("b",)], "k string")
    q.enforce("silver.test", [q.expect_unique(df, "k"), q.expect_not_null(df, "k")])
