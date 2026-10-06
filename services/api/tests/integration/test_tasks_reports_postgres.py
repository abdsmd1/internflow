"""Persistance des tâches et rapports, et garanties de PostgreSQL."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from internflow_api.domain.exceptions import ReportAlreadySubmittedError
from internflow_api.domain.intern import Intern
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.report import IsoWeek, WeeklyReport
from internflow_api.domain.supervisor import Supervisor
from internflow_api.domain.task import Task, TaskStatus
from internflow_api.domain.user import Role, User
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.factories import FIXED_NOW

pytestmark = pytest.mark.integration


def new_uow(engine: Engine) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


@pytest.fixture
def ongoing(engine: Engine) -> tuple[Internship, User]:
    """Un stage en cours et le compte de son encadrant, enregistrés en base."""
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
    account = User(
        email=supervisor.email,
        password_hash="$argon2id$factice",
        role=Role.SUPERVISOR,
        supervisor_id=supervisor.id,
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
        uow.users.add(account)
        uow.internships.add(internship)
        uow.commit()
    return internship, account


WEEK_40 = IsoWeek(2026, 40)


def report(internship: Internship, week: IsoWeek = WEEK_40) -> WeeklyReport:
    return WeeklyReport.submit(
        internship=internship, week=week, accomplishments="Semaine", now=FIXED_NOW
    )


def test_task_round_trip_keeps_completion_time(
    engine: Engine, ongoing: tuple[Internship, User]
) -> None:
    internship, author = ongoing
    task = Task.create(
        internship=internship,
        title="Modéliser",
        due_date=date(2026, 10, 15),
        created_by=author.id,
        now=FIXED_NOW,
    )
    with new_uow(engine) as uow:
        uow.tasks.add(task)
        uow.commit()

    done_at = datetime(2026, 10, 10, 18, 30, tzinfo=UTC)
    task.complete(done_at)
    with new_uow(engine) as uow:
        uow.tasks.save(task)
        uow.commit()

    with new_uow(engine) as uow:
        [loaded] = uow.tasks.list_for_internship(internship.id)
    assert (loaded.status, loaded.completed_at) == (TaskStatus.DONE, done_at)


def test_database_guarantees_one_report_per_week(
    engine: Engine, ongoing: tuple[Internship, User]
) -> None:
    """Simule deux dépôts simultanés : on contourne exists_for_week()."""
    internship, _ = ongoing
    with new_uow(engine) as uow:
        uow.reports.add(report(internship))
        uow.commit()
    with new_uow(engine) as uow, pytest.raises(ReportAlreadySubmittedError):
        uow.reports.add(report(internship))


def test_reports_are_listed_most_recent_week_first(
    engine: Engine, ongoing: tuple[Internship, User]
) -> None:
    internship, _ = ongoing
    with new_uow(engine) as uow:
        for week in (IsoWeek(2026, 40), IsoWeek(2026, 41)):
            uow.reports.add(
                WeeklyReport.submit(
                    internship=internship,
                    week=week,
                    accomplishments="…",
                    now=datetime(2026, 10, 9, tzinfo=UTC),
                )
            )
        uow.commit()
    with new_uow(engine) as uow:
        weeks = [r.week for r in uow.reports.list_for_internship(internship.id)]
    assert weeks == [IsoWeek(2026, 41), IsoWeek(2026, 40)]


def test_task_status_check_constraint(engine: Engine, ongoing: tuple[Internship, User]) -> None:
    internship, author = ongoing
    with engine.begin() as connection, pytest.raises(IntegrityError, match="completed_at_matches"):
        connection.execute(
            text(
                "INSERT INTO tasks (id, internship_id, title, description, due_date, status,"
                " created_by, created_at) VALUES (gen_random_uuid(), :i, 't', '', '2026-10-15',"
                " 'done', :u, now())"
            ),
            {"i": internship.id, "u": author.id},
        )
