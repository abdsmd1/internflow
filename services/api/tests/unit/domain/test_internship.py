from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from internflow_api.domain.exceptions import (
    InternshipNotStartableYetError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import (
    MAX_INTERNSHIP_DAYS,
    DateRange,
    Internship,
    InternshipStatus,
)
from internflow_api.domain.supervisor import SupervisorId

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
TODAY = NOW.date()
PERIOD = DateRange(date(2026, 10, 5), date(2027, 2, 5))


def plan(
    period: DateRange = PERIOD, *, now: datetime = NOW, subject: str = "Agent IA"
) -> Internship:
    return Internship.plan(
        intern_id=InternId(uuid4()),
        supervisor_id=SupervisorId(uuid4()),
        subject=subject,
        period=period,
        now=now,
    )


class TestDateRange:
    def test_days_are_inclusive(self) -> None:
        assert DateRange(date(2026, 1, 1), date(2026, 1, 2)).days == 2

    @pytest.mark.parametrize("end", [date(2026, 1, 1), date(2025, 12, 31)])
    def test_end_must_be_after_start(self, end: date) -> None:
        with pytest.raises(InvalidValueError, match="date de fin"):
            DateRange(date(2026, 1, 1), end)

    @pytest.mark.parametrize(
        ("other", "expected"),
        [
            (DateRange(date(2026, 1, 10), date(2026, 1, 20)), True),  # incluse
            (DateRange(date(2026, 1, 31), date(2026, 2, 10)), True),  # touche le dernier jour
            (DateRange(date(2025, 12, 1), date(2026, 1, 1)), True),  # touche le premier jour
            (DateRange(date(2026, 2, 1), date(2026, 2, 10)), False),  # juste après
            (DateRange(date(2025, 12, 1), date(2025, 12, 31)), False),  # juste avant
        ],
    )
    def test_overlaps(self, other: DateRange, expected: bool) -> None:
        january = DateRange(date(2026, 1, 1), date(2026, 1, 31))
        assert january.overlaps(other) is expected
        assert other.overlaps(january) is expected  # relation symétrique


class TestPlanning:
    def test_new_internship_is_planned(self) -> None:
        internship = plan()
        assert internship.status is InternshipStatus.PLANNED
        assert internship.is_active

    def test_subject_is_required_and_trimmed(self) -> None:
        assert plan(subject="  Agent IA  ").subject == "Agent IA"
        with pytest.raises(InvalidValueError, match="sujet"):
            plan(subject="   ")

    def test_subject_length_is_bounded(self) -> None:
        with pytest.raises(InvalidValueError):
            plan(subject="x" * 201)

    def test_maximum_duration(self) -> None:
        start = date(2026, 10, 5)
        plan(DateRange(start, start + timedelta(days=MAX_INTERNSHIP_DAYS - 1)))
        with pytest.raises(InvalidValueError, match="dépasser"):
            plan(DateRange(start, start + timedelta(days=MAX_INTERNSHIP_DAYS)))

    def test_cannot_plan_an_internship_already_over(self) -> None:
        with pytest.raises(InvalidValueError, match="passée"):
            plan(DateRange(date(2026, 6, 1), date(2026, 9, 30)))

    def test_can_plan_an_internship_ending_today(self) -> None:
        plan(DateRange(date(2026, 9, 1), TODAY))

    def test_creation_date_is_normalized_to_utc(self) -> None:
        paris_time = NOW.astimezone(timezone(timedelta(hours=2)))
        internship = plan(now=paris_time)
        assert internship.created_at == NOW
        assert internship.created_at.tzinfo is UTC


class TestLifecycle:
    def test_start_on_or_after_start_date(self) -> None:
        internship = plan()
        internship.start(today=PERIOD.start)
        assert internship.status is InternshipStatus.ONGOING

    def test_cannot_start_before_start_date(self) -> None:
        internship = plan()
        with pytest.raises(InternshipNotStartableYetError):
            internship.start(today=PERIOD.start - timedelta(days=1))
        assert internship.status is InternshipStatus.PLANNED

    def test_full_happy_path(self) -> None:
        internship = plan()
        internship.start(today=PERIOD.start)
        internship.complete()
        assert internship.status is InternshipStatus.COMPLETED
        assert not internship.is_active

    @pytest.mark.parametrize("status", [InternshipStatus.PLANNED, InternshipStatus.ONGOING])
    def test_active_internship_can_be_cancelled(self, status: InternshipStatus) -> None:
        internship = plan()
        internship.status = status
        internship.cancel()
        assert internship.status is InternshipStatus.CANCELLED

    def test_cannot_complete_a_planned_internship(self) -> None:
        with pytest.raises(InvalidStatusTransitionError, match="terminer"):
            plan().complete()

    @pytest.mark.parametrize("final", [InternshipStatus.COMPLETED, InternshipStatus.CANCELLED])
    def test_final_states_are_frozen(self, final: InternshipStatus) -> None:
        internship = plan()
        internship.status = final
        actions: list[Callable[[], None]] = [
            lambda: internship.start(PERIOD.start),
            internship.complete,
            internship.cancel,
        ]
        for action in actions:
            with pytest.raises(InvalidStatusTransitionError):
                action()
        assert internship.status is final
