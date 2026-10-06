from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from internflow_api.application.interns import RegisterIntern, RegisterInternCommand
from internflow_api.application.internships import (
    ChangeInternshipStatus,
    InternshipAction,
    PlanInternship,
    PlanInternshipCommand,
)
from internflow_api.application.reports import (
    ListReports,
    ReviewReport,
    SubmitReport,
    SubmitReportCommand,
)
from internflow_api.application.supervisors import RegisterSupervisor, RegisterSupervisorCommand
from internflow_api.application.tasks import (
    ChangeTaskStatus,
    CreateTask,
    CreateTaskCommand,
    ListTasks,
    TaskAction,
)
from internflow_api.domain.exceptions import (
    InternshipClosedError,
    InternshipNotFoundError,
    InternshipNotOngoingError,
    InvalidStatusTransitionError,
    PermissionDeniedError,
    ReportAlreadySubmittedError,
    ReportNotFoundError,
    TaskNotFoundError,
)
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.report import IsoWeek, ReportStatus, WeeklyReport
from internflow_api.domain.task import TaskId, TaskStatus
from internflow_api.domain.user import Principal, Role, UserId
from internflow_api.domain.value_objects import StudyLevel
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from tests.factories import HR, FakeClock

WEEK_40 = IsoWeek(2026, 40)  # du 28 septembre au 4 octobre : le stage commence le 1er


@dataclass
class Setup:
    uow: InMemoryUnitOfWork
    clock: FakeClock
    internship: InternshipId
    supervisor: Principal
    intern: Principal
    outsider_supervisor: Principal
    outsider_intern: Principal


@pytest.fixture
def setup(uow: InMemoryUnitOfWork, clock: FakeClock) -> Setup:
    def intern(email: str) -> Principal:
        created = RegisterIntern(uow, clock).execute(
            HR, RegisterInternCommand("Sara", "El Amrani", email, "ENSA", StudyLevel.INGENIEUR)
        )
        return Principal(UserId(uuid4()), Role.INTERN, intern_id=created.id)

    def supervisor(email: str) -> Principal:
        created = RegisterSupervisor(uow, clock).execute(
            HR, RegisterSupervisorCommand("Karim", "Benali", email, "IA")
        )
        return Principal(UserId(uuid4()), Role.SUPERVISOR, supervisor_id=created.id)

    sara, karim = intern("sara@example.com"), supervisor("karim@example.com")
    internship = PlanInternship(uow, clock).execute(
        HR,
        PlanInternshipCommand(
            sara.intern_id,  # type: ignore[arg-type]
            karim.supervisor_id,  # type: ignore[arg-type]
            "Agent IA",
            date(2026, 10, 1),
            date(2027, 2, 28),
        ),
    )
    ChangeInternshipStatus(uow, clock).execute(HR, internship.id, InternshipAction.START)
    return Setup(
        uow,
        clock,
        internship.id,
        supervisor=karim,
        intern=sara,
        outsider_supervisor=supervisor("nadia@example.com"),
        outsider_intern=intern("amine@example.com"),
    )


def create_task(s: Setup, actor: Principal, due: date = date(2026, 10, 15)) -> TaskId:
    return (
        CreateTask(s.uow, s.clock)
        .execute(actor, CreateTaskCommand(s.internship, "Modéliser le schéma", due))
        .task.id
    )


def submit(s: Setup, actor: Principal, week: IsoWeek = WEEK_40) -> WeeklyReport:
    return SubmitReport(s.uow, s.clock).execute(
        actor, SubmitReportCommand(s.internship, week, "Prise en main du projet.")
    )


class TestTasks:
    def test_supervisor_creates_and_intern_completes(self, setup: Setup) -> None:
        task_id = create_task(setup, setup.supervisor)
        change = ChangeTaskStatus(setup.uow, setup.clock)

        assert change.execute(setup.intern, task_id, TaskAction.START).task.status is (
            TaskStatus.IN_PROGRESS
        )
        done = change.execute(setup.intern, task_id, TaskAction.COMPLETE)

        assert done.task.status is TaskStatus.DONE
        assert done.task.completed_at is not None

    def test_created_by_records_the_author(self, setup: Setup) -> None:
        task_id = create_task(setup, setup.supervisor)
        [overview] = ListTasks(setup.uow, setup.clock).execute(HR, setup.internship)
        assert overview.task.id == task_id
        assert overview.task.created_by == setup.supervisor.user_id

    def test_intern_cannot_create_tasks(self, setup: Setup) -> None:
        with pytest.raises(PermissionDeniedError):
            create_task(setup, setup.intern)

    def test_other_supervisor_does_not_see_the_internship(self, setup: Setup) -> None:
        with pytest.raises(InternshipNotFoundError):
            create_task(setup, setup.outsider_supervisor)

    def test_task_of_invisible_internship_looks_nonexistent(self, setup: Setup) -> None:
        task_id = create_task(setup, setup.supervisor)
        with pytest.raises(TaskNotFoundError):
            ChangeTaskStatus(setup.uow, setup.clock).execute(
                setup.outsider_intern, task_id, TaskAction.START
            )

    def test_unknown_task(self, setup: Setup) -> None:
        with pytest.raises(TaskNotFoundError):
            ChangeTaskStatus(setup.uow, setup.clock).execute(HR, TaskId(uuid4()), TaskAction.START)

    def test_listing_is_sorted_by_due_date_and_flags_overdue(self, setup: Setup) -> None:
        create_task(setup, setup.supervisor, date(2026, 11, 30))
        create_task(setup, setup.supervisor, date(2026, 10, 15))
        later = FakeClock(datetime(2026, 11, 2, tzinfo=UTC))

        overviews = ListTasks(setup.uow, later).execute(setup.intern, setup.internship)

        assert [o.task.due_date for o in overviews] == [date(2026, 10, 15), date(2026, 11, 30)]
        assert [o.is_overdue for o in overviews] == [True, False]

    def test_tasks_freeze_when_internship_is_closed(self, setup: Setup) -> None:
        task_id = create_task(setup, setup.supervisor)
        ChangeInternshipStatus(setup.uow, setup.clock).execute(
            HR, setup.internship, InternshipAction.COMPLETE
        )
        with pytest.raises(InternshipClosedError):
            ChangeTaskStatus(setup.uow, setup.clock).execute(
                setup.intern, task_id, TaskAction.COMPLETE
            )
        with pytest.raises(InternshipClosedError):
            create_task(setup, setup.supervisor)


class TestReports:
    def test_intern_submits_and_supervisor_reviews(self, setup: Setup) -> None:
        report = SubmitReport(setup.uow, setup.clock).execute(
            setup.intern,
            SubmitReportCommand(setup.internship, WEEK_40, "Prise en main", "Accès VPN", "Schéma"),
        )
        reviewed = ReviewReport(setup.uow, setup.clock).execute(
            setup.supervisor, report.id, "Bon début."
        )
        assert reviewed.status is ReportStatus.REVIEWED
        [listed] = ListReports(setup.uow).execute(setup.intern, setup.internship)
        assert listed.feedback == "Bon début."

    def test_one_report_per_week(self, setup: Setup) -> None:
        submit(setup, setup.intern)
        with pytest.raises(ReportAlreadySubmittedError):
            submit(setup, setup.intern)

    @pytest.mark.parametrize("actor_name", ["supervisor", "hr"])
    def test_only_the_intern_writes_the_report(self, setup: Setup, actor_name: str) -> None:
        actor = setup.supervisor if actor_name == "supervisor" else HR
        with pytest.raises(PermissionDeniedError):
            submit(setup, actor)

    def test_another_intern_cannot_report_on_this_internship(self, setup: Setup) -> None:
        with pytest.raises(InternshipNotFoundError):
            submit(setup, setup.outsider_intern)

    def test_intern_cannot_review(self, setup: Setup) -> None:
        report = submit(setup, setup.intern)
        with pytest.raises(PermissionDeniedError):
            ReviewReport(setup.uow, setup.clock).execute(setup.intern, report.id, "Auto-éloge")

    def test_outsider_supervisor_cannot_find_the_report(self, setup: Setup) -> None:
        report = submit(setup, setup.intern)
        with pytest.raises(ReportNotFoundError):
            ReviewReport(setup.uow, setup.clock).execute(
                setup.outsider_supervisor,
                report.id,
                "Intrusion",
            )

    def test_review_is_final(self, setup: Setup) -> None:
        report = submit(setup, setup.intern)
        review = ReviewReport(setup.uow, setup.clock)
        review.execute(setup.supervisor, report.id, "OK")
        with pytest.raises(InvalidStatusTransitionError):
            review.execute(HR, report.id, "Encore")

    def test_no_report_once_the_internship_is_over(self, setup: Setup) -> None:
        ChangeInternshipStatus(setup.uow, setup.clock).execute(
            HR, setup.internship, InternshipAction.COMPLETE
        )
        with pytest.raises(InternshipNotOngoingError):
            submit(setup, setup.intern)
