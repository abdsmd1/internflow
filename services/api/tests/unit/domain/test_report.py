from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from internflow_api.domain.exceptions import (
    InternshipNotOngoingError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipStatus
from internflow_api.domain.report import IsoWeek, ReportStatus, WeeklyReport
from internflow_api.domain.supervisor import SupervisorId

NOW = datetime(2026, 10, 14, 17, 0, tzinfo=UTC)  # mercredi de la semaine 2026-W42


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


CURRENT_WEEK = IsoWeek(2026, 42)


def submit(week: IsoWeek = CURRENT_WEEK, **overrides: object) -> WeeklyReport:
    fields: dict[str, object] = {
        "internship": internship(),
        "week": week,
        "accomplishments": "Mise en place du pipeline d'ingestion.",
        "now": NOW,
    }
    fields.update(overrides)
    return WeeklyReport.submit(**fields)  # type: ignore[arg-type]


class TestIsoWeek:
    def test_of_a_date(self) -> None:
        assert IsoWeek.of(date(2026, 10, 14)) == IsoWeek(2026, 42)

    def test_week_bounds(self) -> None:
        week = IsoWeek(2026, 42)
        assert (week.monday, week.sunday) == (date(2026, 10, 12), date(2026, 10, 18))

    def test_year_boundary_follows_iso_rules(self) -> None:
        # Le 1er janvier 2027 (vendredi) appartient à la dernière semaine de 2026.
        assert IsoWeek.of(date(2027, 1, 1)) == IsoWeek(2026, 53)

    def test_parse_and_format(self) -> None:
        assert IsoWeek.parse(" 2026-W07 ") == IsoWeek(2026, 7)
        assert str(IsoWeek(2026, 7)) == "2026-W07"

    @pytest.mark.parametrize("text", ["2026-42", "2026W42", "26-W42", "2026-W5"])
    def test_parse_rejects_bad_format(self, text: str) -> None:
        with pytest.raises(InvalidValueError, match="AAAA-Wss"):
            IsoWeek.parse(text)

    @pytest.mark.parametrize(("year", "week"), [(2026, 0), (2025, 53), (2026, 54)])
    def test_rejects_weeks_that_do_not_exist(self, year: int, week: int) -> None:
        with pytest.raises(InvalidValueError, match="Semaine ISO invalide"):
            IsoWeek(year, week)

    def test_weeks_are_ordered(self) -> None:
        assert IsoWeek(2026, 52) < IsoWeek(2026, 53) < IsoWeek(2027, 1)


class TestSubmission:
    def test_submitted_report(self) -> None:
        report = submit(difficulties="  Accès aux données  ")
        assert report.status is ReportStatus.SUBMITTED
        assert report.difficulties == "Accès aux données"
        assert report.feedback is None

    def test_internship_must_be_ongoing(self) -> None:
        for status in (InternshipStatus.PLANNED, InternshipStatus.COMPLETED):
            with pytest.raises(InternshipNotOngoingError):
                submit(internship=internship(status))

    def test_first_partial_week_of_internship_is_accepted(self) -> None:
        submit(IsoWeek(2026, 40))  # stage commencé le jeudi 1er octobre

    def test_week_before_internship_is_rejected(self) -> None:
        with pytest.raises(InvalidValueError, match="en dehors"):
            submit(IsoWeek(2026, 39))

    def test_future_week_is_rejected(self) -> None:
        with pytest.raises(InvalidValueError, match="pas encore commencé"):
            submit(IsoWeek(2026, 43))

    def test_accomplishments_are_required(self) -> None:
        with pytest.raises(InvalidValueError, match="réalisations"):
            submit(accomplishments="   ")

    def test_text_fields_are_bounded(self) -> None:
        with pytest.raises(InvalidValueError):
            submit(next_steps="x" * 5001)


class TestReview:
    def test_review_adds_feedback(self) -> None:
        report = submit()
        report.review("  Bon avancement, documenter le schéma.  ", NOW)
        assert report.status is ReportStatus.REVIEWED
        assert report.feedback == "Bon avancement, documenter le schéma."
        assert report.reviewed_at == NOW

    def test_feedback_is_required(self) -> None:
        with pytest.raises(InvalidValueError, match="retour"):
            submit().review("  ", NOW)

    def test_cannot_review_twice(self) -> None:
        report = submit()
        report.review("OK", NOW)
        with pytest.raises(InvalidStatusTransitionError, match="relire"):
            report.review("Encore", NOW)
