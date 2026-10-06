from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from internflow_api.domain.exceptions import (
    InternshipClosedError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.task import Task, TaskStatus
from internflow_api.domain.user import UserId

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
AUTHOR = UserId(uuid4())


def internship(status: InternshipStatus = InternshipStatus.ONGOING) -> Internship:
    result = Internship.plan(
        intern_id=InternId(uuid4()),
        supervisor_id=SupervisorId(uuid4()),
        subject="Agent IA",
        period=DateRange(date(2026, 10, 1), date(2027, 2, 28)),
        now=NOW,
    )
    result.status = status
    return result


def create(due: date = date(2026, 10, 15), **overrides: object) -> Task:
    fields: dict[str, object] = {
        "internship": internship(),
        "title": "Modéliser le schéma de données",
        "due_date": due,
        "created_by": AUTHOR,
        "now": NOW,
    }
    fields.update(overrides)
    return Task.create(**fields)  # type: ignore[arg-type]


class TestCreation:
    def test_new_task_is_todo(self) -> None:
        task = create(description="  Tables et relations  ")
        assert (task.status, task.description, task.completed_at) == (
            TaskStatus.TODO,
            "Tables et relations",
            None,
        )

    @pytest.mark.parametrize("due", [date(2026, 10, 1), date(2027, 2, 28)])
    def test_due_date_on_period_bounds_is_accepted(self, due: date) -> None:
        create(due)

    @pytest.mark.parametrize("due", [date(2026, 9, 30), date(2027, 3, 1)])
    def test_due_date_outside_internship_is_rejected(self, due: date) -> None:
        with pytest.raises(InvalidValueError, match="période du stage"):
            create(due)

    @pytest.mark.parametrize("status", [InternshipStatus.COMPLETED, InternshipStatus.CANCELLED])
    def test_closed_internship_gets_no_new_task(self, status: InternshipStatus) -> None:
        with pytest.raises(InternshipClosedError):
            create(internship=internship(status))

    def test_title_is_required_and_bounded(self) -> None:
        with pytest.raises(InvalidValueError, match="titre"):
            create(title="  ")
        with pytest.raises(InvalidValueError):
            create(title="x" * 151)

    def test_description_is_bounded(self) -> None:
        with pytest.raises(InvalidValueError):
            create(description="x" * 2001)


class TestLifecycle:
    def test_start_then_complete(self) -> None:
        task = create()
        task.start()
        task.complete(datetime(2026, 10, 10, 18, 0, tzinfo=UTC))
        assert task.status is TaskStatus.DONE
        assert task.completed_at == datetime(2026, 10, 10, 18, 0, tzinfo=UTC)

    def test_can_complete_directly_from_todo(self) -> None:
        task = create()
        task.complete(NOW)
        assert task.status is TaskStatus.DONE

    def test_cannot_start_twice(self) -> None:
        task = create()
        task.start()
        with pytest.raises(InvalidStatusTransitionError, match="commencer"):
            task.start()

    def test_done_is_final(self) -> None:
        task = create()
        task.complete(NOW)
        with pytest.raises(InvalidStatusTransitionError):
            task.complete(NOW)
        with pytest.raises(InvalidStatusTransitionError):
            task.start()

    def test_completion_date_consistency_is_enforced(self) -> None:
        with pytest.raises(InvalidValueError, match="date de réalisation"):
            Task(
                internship_id=internship().id,
                title="Incohérente",
                due_date=date(2026, 10, 15),
                created_by=AUTHOR,
                created_at=NOW,
                status=TaskStatus.DONE,
            )


class TestOverdue:
    def test_overdue_when_past_due_and_not_done(self) -> None:
        task = create(date(2026, 10, 15))
        assert not task.is_overdue(date(2026, 10, 15))
        assert task.is_overdue(date(2026, 10, 16))

    def test_done_task_is_never_overdue(self) -> None:
        task = create(date(2026, 10, 15))
        task.complete(NOW)
        assert not task.is_overdue(date(2026, 12, 1))
