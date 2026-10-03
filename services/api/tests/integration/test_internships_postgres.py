"""Garanties apportées par PostgreSQL pour les stages.

Ces tests contournent volontairement les vérifications applicatives pour prouver
que la base protège les règles critiques, même en cas de requêtes concurrentes.
"""

from __future__ import annotations

import threading
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from internflow_api.application.internships import (
    ChangeInternshipStatus,
    InternshipAction,
    ListInternships,
    PlanInternship,
    PlanInternshipCommand,
)
from internflow_api.domain.exceptions import (
    InternshipOverlapError,
    SupervisorCapacityExceededError,
)
from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.factories import FIXED_NOW, HR, FakeClock

pytestmark = pytest.mark.integration

OCT = DateRange(date(2026, 10, 5), date(2027, 2, 5))


def new_uow(engine: Engine) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


def seed(
    engine: Engine, *, max_interns: int = 5, interns: int = 1
) -> tuple[list[InternId], SupervisorId]:
    supervisor = Supervisor(
        name=PersonName("Karim", "Benali"),
        email=Email(f"{uuid4().hex[:8]}@example.com"),
        department="IA",
        max_interns=max_interns,
        created_at=FIXED_NOW,
    )
    created = [
        Intern(
            name=PersonName("Sara", "El Amrani"),
            email=Email(f"{uuid4().hex[:8]}@example.com"),
            school="ENSA",
            study_level=StudyLevel.INGENIEUR,
            created_at=FIXED_NOW,
        )
        for _ in range(interns)
    ]
    with new_uow(engine) as uow:
        uow.supervisors.add(supervisor)
        for intern in created:
            uow.interns.add(intern)
        uow.commit()
    return [i.id for i in created], supervisor.id


def internship(
    intern_id: InternId, supervisor_id: SupervisorId, period: DateRange = OCT
) -> Internship:
    return Internship.plan(
        intern_id=intern_id,
        supervisor_id=supervisor_id,
        subject="Agent IA",
        period=period,
        now=FIXED_NOW,
    )


class TestExclusionConstraint:
    def test_database_rejects_overlapping_active_internships(self, engine: Engine) -> None:
        """Simule une course : on n'appelle pas has_active_overlap()."""
        [intern], supervisor = seed(engine)
        with new_uow(engine) as uow:
            uow.internships.add(internship(intern, supervisor))
            uow.commit()

        overlapping = internship(intern, supervisor, DateRange(date(2027, 2, 5), date(2027, 4, 1)))
        with new_uow(engine) as uow, pytest.raises(InternshipOverlapError):
            uow.internships.add(overlapping)

    def test_cancelled_internships_are_ignored(self, engine: Engine) -> None:
        [intern], supervisor = seed(engine)
        cancelled = internship(intern, supervisor)
        cancelled.cancel()
        with new_uow(engine) as uow:
            uow.internships.add(cancelled)
            uow.internships.add(internship(intern, supervisor))
            uow.commit()

    def test_reactivating_an_overlap_is_rejected_on_save(self, engine: Engine) -> None:
        [intern], supervisor = seed(engine)
        cancelled = internship(intern, supervisor)
        cancelled.cancel()
        with new_uow(engine) as uow:
            uow.internships.add(cancelled)
            uow.internships.add(internship(intern, supervisor))
            uow.commit()

        cancelled.status = InternshipStatus.PLANNED  # contourne la machine à états
        with new_uow(engine) as uow, pytest.raises(InternshipOverlapError):
            uow.internships.save(cancelled)

    def test_period_check_constraint(self, engine: Engine) -> None:
        [intern], supervisor = seed(engine)
        broken = internship(intern, supervisor, DateRange(date(2026, 11, 1), date(2026, 12, 1)))
        object.__setattr__(broken.period, "end", broken.period.start)  # contourne le domaine
        with new_uow(engine) as uow, pytest.raises(IntegrityError, match="period_valid"):
            uow.internships.add(broken)


class TestSupervisorLock:
    def test_concurrent_assignments_cannot_exceed_capacity(self, engine: Engine) -> None:
        """Le verrou FOR UPDATE met la 2e affectation en attente jusqu'au commit de la 1re."""
        (first_intern, second_intern), supervisor = seed(engine, max_interns=1, interns=2)
        lock_taken = threading.Event()
        release = threading.Event()
        outcome: dict[str, object] = {}

        def first_transaction() -> None:
            with new_uow(engine) as uow:
                uow.supervisors.get(supervisor, for_update=True)
                lock_taken.set()
                release.wait(timeout=10)
                uow.internships.add(internship(first_intern, supervisor))
                uow.commit()

        def second_transaction() -> None:
            try:
                PlanInternship(new_uow(engine), FakeClock()).execute(
                    HR,
                    PlanInternshipCommand(
                        second_intern, supervisor, "Agent IA", OCT.start, OCT.end
                    ),
                )
                outcome["result"] = "planned"
            except SupervisorCapacityExceededError as error:
                outcome["result"] = error

        first = threading.Thread(target=first_transaction)
        first.start()
        assert lock_taken.wait(timeout=10)
        second = threading.Thread(target=second_transaction)
        second.start()

        second.join(timeout=0.5)
        assert second.is_alive(), "la 2e transaction aurait dû attendre le verrou"

        release.set()
        first.join(timeout=10)
        second.join(timeout=10)
        assert isinstance(outcome["result"], SupervisorCapacityExceededError)


class TestInternshipQueries:
    def test_filters_and_status_persistence(self, engine: Engine) -> None:
        (sara, amine), karim = seed(engine, interns=2)
        clock = FakeClock(datetime(2026, 10, 5, tzinfo=UTC))
        plan = PlanInternship(new_uow(engine), FakeClock())
        first = plan.execute(HR, PlanInternshipCommand(sara, karim, "Agent IA", OCT.start, OCT.end))
        plan.execute(HR, PlanInternshipCommand(amine, karim, "ETL Spark", OCT.start, OCT.end))

        ChangeInternshipStatus(new_uow(engine), clock).execute(HR, first.id, InternshipAction.START)

        listing = ListInternships(new_uow(engine))
        assert listing.execute(HR, InternshipFilter(supervisor_id=karim)).total == 2
        ongoing = listing.execute(HR, InternshipFilter(status=InternshipStatus.ONGOING))
        assert [i.id for i in ongoing.items] == [first.id]
        assert ongoing.items[0].period == OCT
