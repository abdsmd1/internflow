"""Recherche sémantique sur un vrai PostgreSQL avec l'extension pgvector."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from internflow_api import cli
from internflow_api.application.report_search import (
    ReportIndexer,
    SearchReports,
    SearchReportsQuery,
)
from internflow_api.domain.intern import Intern
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.report import IsoWeek, WeeklyReport
from internflow_api.domain.report_search import ReportSection
from internflow_api.domain.supervisor import Supervisor
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.orm import ReportPassageRecord
from internflow_api.infrastructure.persistence.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.factories import FIXED_NOW, HR
from tests.fake_embedder import KeywordEmbedder

pytestmark = pytest.mark.integration

EMBEDDER = KeywordEmbedder()


def new_uow(engine: Engine) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


def ongoing_internship(engine: Engine) -> Internship:
    intern = Intern(
        name=PersonName("Sara", "El Amrani"),
        email=Email(f"{uuid4().hex[:8]}@example.com"),
        school="ENSA",
        study_level=StudyLevel.INGENIEUR,
        created_at=FIXED_NOW,
    )
    supervisor = Supervisor(
        name=PersonName("Karim", "Benali"),
        email=Email(f"{uuid4().hex[:8]}@example.com"),
        department="IA",
        created_at=FIXED_NOW,
    )
    internship = Internship.plan(
        intern_id=intern.id,
        supervisor_id=supervisor.id,
        subject="Agent IA",
        period=DateRange(date(2026, 10, 1), date(2027, 2, 28)),
        now=FIXED_NOW,
    )
    internship.status = InternshipStatus.ONGOING
    with new_uow(engine) as uow:
        uow.interns.add(intern)
        uow.supervisors.add(supervisor)
        uow.internships.add(internship)
        uow.commit()
    return internship


def store_report(
    engine: Engine, internship: Internship, difficulties: str, *, indexed: bool = True
) -> WeeklyReport:
    report = WeeklyReport.submit(
        internship=internship,
        week=IsoWeek(2026, 40),
        accomplishments="Semaine de travail.",
        difficulties=difficulties,
        now=FIXED_NOW,
    )
    with new_uow(engine) as uow:
        uow.reports.add(report)
        if indexed:
            ReportIndexer(EMBEDDER).index(uow, report)
        uow.commit()
    return report


def passage_count(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(ReportPassageRecord)) or 0


def test_vectors_are_stored_and_ranked_by_cosine_distance(engine: Engine) -> None:
    internship = ongoing_internship(engine)
    report = store_report(engine, internship, "Réseau Docker instable entre conteneurs.")

    hits = SearchReports(new_uow(engine), EMBEDDER, min_score=0.0).execute(
        HR, SearchReportsQuery("conteneurs Docker")
    )

    assert hits[0].passage.report_id == report.id
    assert hits[0].passage.section is ReportSection.DIFFICULTIES
    assert hits[0].passage.week == IsoWeek(2026, 40)
    assert hits[0].passage.internship_id == internship.id
    assert hits[0].score > hits[-1].score


def test_permissions_are_applied_inside_the_sql_query(engine: Engine) -> None:
    mine = ongoing_internship(engine)
    other = ongoing_internship(engine)
    store_report(engine, mine, "Docker refuse de démarrer.")
    store_report(engine, other, "Docker refuse de démarrer.")
    supervisor = Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=mine.supervisor_id)

    hits = SearchReports(new_uow(engine), EMBEDDER, min_score=0.3).execute(
        supervisor, SearchReportsQuery("Docker")
    )

    assert {h.passage.internship_id for h in hits} == {mine.id}


def test_status_and_threshold_filters(engine: Engine) -> None:
    internship = ongoing_internship(engine)
    store_report(engine, internship, "Docker refuse de démarrer.")
    query = EMBEDDER.embed_query("Docker")
    with new_uow(engine) as uow:
        ongoing = uow.passages.search(
            query,
            InternshipFilter(status=InternshipStatus.ONGOING),
            internship_id=internship.id,
            limit=5,
            min_score=0.3,
        )
        planned = uow.passages.search(
            query,
            InternshipFilter(status=InternshipStatus.PLANNED),
            internship_id=None,
            limit=5,
            min_score=0.3,
        )
        strict = uow.passages.search(
            query, InternshipFilter(), internship_id=None, limit=5, min_score=0.999
        )
    assert [h.passage.content for h in ongoing] == ["Docker refuse de démarrer."]
    assert planned == strict == []


def test_reindexing_replaces_passages_and_deleting_a_report_cascades(engine: Engine) -> None:
    internship = ongoing_internship(engine)
    report = store_report(engine, internship, "Docker refuse de démarrer.")
    with new_uow(engine) as uow:
        ReportIndexer(EMBEDDER).index(uow, report)  # deux fois : pas de doublon
        uow.commit()
    assert passage_count(engine) == 2

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM weekly_reports"))
    assert passage_count(engine) == 0


def test_cli_rebuilds_the_index_of_imported_reports(
    engine: Engine,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Cas réel : le générateur de données écrit des rapports sans les indexer.
    store_report(engine, ongoing_internship(engine), "Docker en panne.", indexed=False)
    assert passage_count(engine) == 0
    monkeypatch.setenv("INTERNFLOW_DATABASE_URL", database_url)

    assert cli.main(["reindex-reports"], embedder=EMBEDDER) == 0

    assert "1 rapports, 2 passages" in capsys.readouterr().out
    assert passage_count(engine) == 2


def test_cli_reports_a_model_outage(
    engine: Engine,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_report(engine, ongoing_internship(engine), "Docker en panne.", indexed=False)
    monkeypatch.setenv("INTERNFLOW_DATABASE_URL", database_url)

    assert cli.main(["reindex-reports"], embedder=KeywordEmbedder(available=False)) == 1

    assert "hors service" in capsys.readouterr().err
