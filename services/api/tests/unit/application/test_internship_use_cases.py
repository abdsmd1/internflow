from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from internflow_api.application.interns import RegisterIntern, RegisterInternCommand
from internflow_api.application.internships import (
    ChangeInternshipStatus,
    GetInternship,
    InternshipAction,
    ListInternships,
    PlanInternship,
    PlanInternshipCommand,
)
from internflow_api.application.supervisors import RegisterSupervisor, RegisterSupervisorCommand
from internflow_api.domain.exceptions import (
    InternNotFoundError,
    InternshipNotFoundError,
    InternshipNotStartableYetError,
    InternshipOverlapError,
    InvalidStatusTransitionError,
    SupervisorCapacityExceededError,
    SupervisorNotFoundError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import InternshipId, InternshipStatus
from internflow_api.domain.ports.repositories import InternshipFilter
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.value_objects import StudyLevel
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from tests.factories import HR, FakeClock

OCT = (date(2026, 10, 5), date(2027, 2, 5))
MARCH = (date(2027, 3, 1), date(2027, 6, 30))


class World:
    """Petit « monde » de test : crée stagiaires et encadrants à la demande."""

    def __init__(self, uow: InMemoryUnitOfWork, clock: FakeClock) -> None:
        self.uow = uow
        self.clock = clock
        self._counter = 0

    def intern(self) -> InternId:
        self._counter += 1
        return (
            RegisterIntern(self.uow, self.clock)
            .execute(
                HR,
                RegisterInternCommand(
                    "Sara",
                    "El Amrani",
                    f"s{self._counter}@example.com",
                    "ENSA",
                    StudyLevel.INGENIEUR,
                ),
            )
            .id
        )

    def supervisor(self, max_interns: int = 5) -> SupervisorId:
        self._counter += 1
        return (
            RegisterSupervisor(self.uow, self.clock)
            .execute(
                HR,
                RegisterSupervisorCommand(
                    "Karim", "Benali", f"e{self._counter}@example.com", "IA", max_interns
                ),
            )
            .id
        )

    def plan(
        self,
        intern_id: InternId,
        supervisor_id: SupervisorId,
        period: tuple[date, date] = OCT,
    ) -> InternshipId:
        return (
            PlanInternship(self.uow, self.clock)
            .execute(
                HR, PlanInternshipCommand(intern_id, supervisor_id, "Agent IA de suivi", *period)
            )
            .id
        )


@pytest.fixture
def world(uow: InMemoryUnitOfWork, clock: FakeClock) -> World:
    return World(uow, clock)


class TestPlanInternship:
    def test_plans_a_new_internship(self, world: World) -> None:
        internship_id = world.plan(world.intern(), world.supervisor())

        internship = GetInternship(world.uow).execute(HR, internship_id)
        assert internship.status is InternshipStatus.PLANNED
        assert internship.period.days == 124

    def test_unknown_intern(self, world: World) -> None:
        with pytest.raises(InternNotFoundError):
            world.plan(InternId(uuid4()), world.supervisor())

    def test_unknown_supervisor(self, world: World) -> None:
        with pytest.raises(SupervisorNotFoundError):
            world.plan(world.intern(), SupervisorId(uuid4()))

    def test_intern_cannot_have_two_overlapping_internships(self, world: World) -> None:
        intern = world.intern()
        world.plan(intern, world.supervisor())

        with pytest.raises(InternshipOverlapError):
            world.plan(intern, world.supervisor(), (date(2027, 1, 1), date(2027, 3, 1)))

    def test_intern_can_chain_internships(self, world: World) -> None:
        intern = world.intern()
        world.plan(intern, world.supervisor(), OCT)
        world.plan(intern, world.supervisor(), MARCH)

        assert ListInternships(world.uow).execute(HR, InternshipFilter(intern_id=intern)).total == 2

    def test_cancelled_internship_frees_the_period(self, world: World) -> None:
        intern = world.intern()
        first = world.plan(intern, world.supervisor())
        ChangeInternshipStatus(world.uow, world.clock).execute(HR, first, InternshipAction.CANCEL)

        world.plan(intern, world.supervisor())  # ne lève pas d'exception

    def test_supervisor_capacity_is_enforced(self, world: World) -> None:
        supervisor = world.supervisor(max_interns=2)
        world.plan(world.intern(), supervisor)
        world.plan(world.intern(), supervisor)

        with pytest.raises(SupervisorCapacityExceededError):
            world.plan(world.intern(), supervisor)

    def test_capacity_only_counts_overlapping_periods(self, world: World) -> None:
        supervisor = world.supervisor(max_interns=1)
        world.plan(world.intern(), supervisor, OCT)
        world.plan(world.intern(), supervisor, MARCH)  # autre période : accepté

    def test_rejected_planning_leaves_no_trace(self, world: World) -> None:
        supervisor = world.supervisor(max_interns=1)
        world.plan(world.intern(), supervisor)
        with pytest.raises(SupervisorCapacityExceededError):
            world.plan(world.intern(), supervisor)

        assert ListInternships(world.uow).execute(HR).total == 1


class TestListInternships:
    def test_filters_combine(self, world: World) -> None:
        karim, nadia = world.supervisor(), world.supervisor()
        sara = world.intern()
        world.plan(sara, karim, OCT)
        world.plan(sara, nadia, MARCH)
        world.plan(world.intern(), karim, OCT)

        by_karim = ListInternships(world.uow).execute(HR, InternshipFilter(supervisor_id=karim))
        sara_with_karim = ListInternships(world.uow).execute(
            HR, InternshipFilter(intern_id=sara, supervisor_id=karim)
        )
        planned = ListInternships(world.uow).execute(
            HR, InternshipFilter(status=InternshipStatus.PLANNED)
        )
        ongoing = ListInternships(world.uow).execute(
            HR, InternshipFilter(status=InternshipStatus.ONGOING)
        )

        assert (by_karim.total, sara_with_karim.total, planned.total, ongoing.total) == (2, 1, 3, 0)


class TestChangeInternshipStatus:
    def test_lifecycle(self, world: World) -> None:
        internship_id = world.plan(world.intern(), world.supervisor())
        after_start = FakeClock(datetime(2026, 10, 5, 8, 0, tzinfo=UTC))
        change = ChangeInternshipStatus(world.uow, after_start)

        assert (
            change.execute(HR, internship_id, InternshipAction.START).status
            is InternshipStatus.ONGOING
        )
        completed = change.execute(HR, internship_id, InternshipAction.COMPLETE)

        assert completed.status is InternshipStatus.COMPLETED
        assert (
            GetInternship(world.uow).execute(HR, internship_id).status is InternshipStatus.COMPLETED
        )

    def test_cannot_start_before_start_date(self, world: World) -> None:
        internship_id = world.plan(world.intern(), world.supervisor())  # horloge : 1er octobre

        with pytest.raises(InternshipNotStartableYetError):
            ChangeInternshipStatus(world.uow, world.clock).execute(
                HR, internship_id, InternshipAction.START
            )
        assert (
            GetInternship(world.uow).execute(HR, internship_id).status is InternshipStatus.PLANNED
        )

    def test_refused_transition_is_not_saved(self, world: World) -> None:
        internship_id = world.plan(world.intern(), world.supervisor())
        with pytest.raises(InvalidStatusTransitionError):
            ChangeInternshipStatus(world.uow, world.clock).execute(
                HR, internship_id, InternshipAction.COMPLETE
            )

    def test_unknown_internship(self, world: World) -> None:
        with pytest.raises(InternshipNotFoundError):
            ChangeInternshipStatus(world.uow, world.clock).execute(
                HR, InternshipId(uuid4()), InternshipAction.CANCEL
            )

    def test_get_unknown_internship(self, world: World) -> None:
        with pytest.raises(InternshipNotFoundError):
            GetInternship(world.uow).execute(HR, InternshipId(uuid4()))
