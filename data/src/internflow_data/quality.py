"""Contrôles de qualité des données, exécutés à chaque passage de couche.

Un jeu de données qui viole une règle n'est **jamais** publié : le job s'arrête
avec la liste des contrôles en échec (principe « fail fast »).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    failing_rows: int

    @property
    def passed(self) -> bool:
        return self.failing_rows == 0


class DataQualityError(Exception):
    def __init__(self, dataset: str, failures: Sequence[CheckResult]) -> None:
        details = ", ".join(f"{f.name} ({f.failing_rows} ligne(s))" for f in failures)
        super().__init__(f"Qualité insuffisante pour « {dataset} » : {details}.")
        self.dataset = dataset
        self.failures = failures


def _count(df: DataFrame, condition: Column) -> int:
    return df.filter(condition).count()


def expect_not_null(df: DataFrame, *columns: str) -> list[CheckResult]:
    return [CheckResult(f"{c} non nul", _count(df, F.col(c).isNull())) for c in columns]


def expect_unique(df: DataFrame, *columns: str) -> CheckResult:
    duplicates = df.groupBy(*columns).count().filter(F.col("count") > 1).count()
    return CheckResult(f"unicité de ({', '.join(columns)})", duplicates)


def expect_in(df: DataFrame, column: str, allowed: Iterable[str]) -> CheckResult:
    values = sorted(allowed)
    return CheckResult(f"{column} ∈ {values}", _count(df, ~F.col(column).isin(values)))


def expect_between(df: DataFrame, column: str, low: float, high: float) -> CheckResult:
    outside = F.col(column).isNotNull() & ~F.col(column).between(low, high)
    return CheckResult(f"{column} ∈ [{low}, {high}]", _count(df, outside))


def expect(df: DataFrame, name: str, condition: Column) -> CheckResult:
    """Règle libre : `condition` décrit les lignes VALIDES."""
    return CheckResult(name, _count(df, ~condition))


def enforce(dataset: str, results: Iterable[CheckResult | list[CheckResult]]) -> None:
    flat: list[CheckResult] = []
    for result in results:
        flat.extend(result if isinstance(result, list) else [result])
    failures = [r for r in flat if not r.passed]
    if failures:
        raise DataQualityError(dataset, failures)
