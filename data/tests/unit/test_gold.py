"""Indicateurs gold sur un petit jeu de données silver construit à la main.

Chaque valeur attendue se vérifie de tête : c'est tout l'intérêt de ces tests.
"""

from datetime import date

import pytest
from pyspark.sql import DataFrame, Row, SparkSession

from internflow_data.transformations import gold

AS_OF = date(2026, 10, 21)  # mercredi de la semaine 2026-W43


@pytest.fixture
def silver(spark: SparkSession) -> dict[str, DataFrame]:
    internships = spark.createDataFrame(
        [
            # Stage A : commencé le lundi 28/09 (W40), en cours.
            Row(
                internship_key="A",
                intern_key="a",
                supervisor_key="K",
                status="ongoing",
                start_date=date(2026, 9, 28),
                end_date=date(2027, 1, 31),
                duration_days=126,
            ),
            # Stage B : prévu, ne doit pas apparaître dans les indicateurs de stage.
            Row(
                internship_key="B",
                intern_key="b",
                supervisor_key="K",
                status="planned",
                start_date=date(2026, 11, 2),
                end_date=date(2027, 2, 26),
                duration_days=117,
            ),
            # Stage C : en cours, sans aucune activité.
            Row(
                internship_key="C",
                intern_key="c",
                supervisor_key="N",
                status="ongoing",
                start_date=date(2026, 10, 19),
                end_date=date(2027, 1, 29),
                duration_days=103,
            ),
        ]
    )
    supervisors = spark.createDataFrame(
        [
            Row(supervisor_key="K", department="Data & IA", max_interns=4),
            Row(supervisor_key="N", department="Web", max_interns=2),
        ]
    )
    tasks = spark.createDataFrame(
        [
            Row(
                task_key="t1",
                internship_key="A",
                status="done",
                due_date=date(2026, 10, 9),
                created_date=date(2026, 9, 30),
                completed_date=date(2026, 10, 8),
                delay_days=-1,
            ),
            Row(
                task_key="t2",
                internship_key="A",
                status="done",
                due_date=date(2026, 10, 14),
                created_date=date(2026, 10, 1),
                completed_date=date(2026, 10, 17),
                delay_days=3,
            ),
            Row(
                task_key="t3",
                internship_key="A",
                status="in_progress",
                due_date=date(2026, 10, 20),
                created_date=date(2026, 10, 5),
                completed_date=None,
                delay_days=None,
            ),
            Row(
                task_key="t4",
                internship_key="A",
                status="todo",
                due_date=date(2026, 11, 6),
                created_date=date(2026, 10, 12),
                completed_date=None,
                delay_days=None,
            ),
        ],
        "task_key string, internship_key string, status string, due_date date, "
        "created_date date, completed_date date, delay_days int",
    )
    reports = spark.createDataFrame(
        [
            Row(
                report_key="r1",
                internship_key="A",
                iso_year=2026,
                iso_week=40,
                week_start=date(2026, 9, 28),
                status="reviewed",
                submitted_date=date(2026, 10, 2),
                review_lag_days=2,
            ),
            Row(
                report_key="r2",
                internship_key="A",
                iso_year=2026,
                iso_week=42,
                week_start=date(2026, 10, 12),
                status="submitted",
                submitted_date=date(2026, 10, 16),
                review_lag_days=None,
            ),
        ],
        "report_key string, internship_key string, iso_year int, iso_week int, week_start date, "
        "status string, submitted_date date, review_lag_days int",
    )
    return {
        "internships": internships,
        "supervisors": supervisors,
        "tasks": tasks,
        "reports": reports,
    }


def kpis_by_key(silver: dict[str, DataFrame]) -> dict[str, Row]:
    df = gold.internship_kpis(
        silver["internships"], silver["supervisors"], silver["tasks"], silver["reports"], AS_OF
    )
    return {row.internship_key: row for row in df.collect()}


class TestInternshipKpis:
    def test_only_measurable_internships(self, silver: dict[str, DataFrame]) -> None:
        assert set(kpis_by_key(silver)) == {"A", "C"}

    def test_task_indicators(self, silver: dict[str, DataFrame]) -> None:
        a = kpis_by_key(silver)["A"]
        assert (a.tasks_total, a.tasks_done, a.tasks_done_on_time) == (4, 2, 1)
        assert a.on_time_rate == 0.5
        assert a.overdue_open_tasks == 1  # t3 : échéance 20/10 dépassée le 21/10
        assert a.avg_delay_days == 1.0  # (-1 + 3) / 2

    def test_report_indicators(self, silver: dict[str, DataFrame]) -> None:
        a = kpis_by_key(silver)["A"]
        # Semaines terminées au 21/10 : W40, W41, W42 → 3 rapports attendus, 2 déposés.
        assert (a.reports_expected, a.reports_submitted, a.reports_reviewed) == (3, 2, 1)
        assert a.report_regularity == pytest.approx(0.6667)
        assert a.avg_review_lag_days == 2.0

    def test_internship_without_activity(self, silver: dict[str, DataFrame]) -> None:
        c = kpis_by_key(silver)["C"]
        assert (c.tasks_total, c.reports_submitted, c.overdue_open_tasks) == (0, 0, 0)
        assert c.on_time_rate is None  # pas de division par zéro
        assert c.reports_expected == 0  # la première semaine n'est pas terminée
        assert c.report_regularity is None
        assert c.department == "Web"


class TestExpectedReports:
    @pytest.mark.parametrize(
        ("start", "end", "expected"),
        [
            (date(2026, 9, 28), date(2027, 1, 31), 3),  # en cours
            (date(2026, 7, 6), date(2026, 8, 28), 8),  # terminé : borné par la fin
            (date(2026, 10, 19), date(2027, 1, 29), 0),  # première semaine en cours
            (date(2026, 10, 1), date(2027, 1, 31), 3),  # début un jeudi : W40 compte
        ],
    )
    def test_counts_completed_iso_weeks(
        self, spark: SparkSession, start: date, end: date, expected: int
    ) -> None:
        df = spark.createDataFrame([Row(s=start, e=end)])
        [row] = df.select(gold.expected_reports(df.s, df.e, AS_OF).alias("n")).collect()
        assert row.n == expected


class TestSupervisorWorkload:
    def test_load_and_pending_reviews(self, silver: dict[str, DataFrame]) -> None:
        rows = {
            r.supervisor_key: r
            for r in gold.supervisor_workload(
                silver["internships"], silver["supervisors"], silver["reports"], AS_OF
            ).collect()
        }
        assert (rows["K"].active_internships, rows["K"].utilization, rows["K"].pending_reviews) == (
            1,
            0.25,
            1,
        )
        assert (rows["N"].active_internships, rows["N"].utilization, rows["N"].pending_reviews) == (
            1,
            0.5,
            0,
        )


class TestWeeklyActivity:
    def test_counts_per_iso_week(self, silver: dict[str, DataFrame]) -> None:
        rows = [
            (r.iso_year, r.iso_week, r.reports_submitted, r.tasks_completed)
            for r in gold.weekly_activity(silver["tasks"], silver["reports"], AS_OF).collect()
        ]
        # t1 terminée le 08/10 (W41), t2 le 17/10 (W42) ; rapports en W40 et W42.
        assert rows == [(2026, 40, 1, 0), (2026, 41, 0, 1), (2026, 42, 1, 1)]
