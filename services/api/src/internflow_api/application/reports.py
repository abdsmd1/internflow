"""Cas d'usage liés aux rapports hebdomadaires."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from internflow_api.application.internships import load_visible_internship
from internflow_api.domain.authorization import (
    can_view_internship,
    ensure_can_submit_report,
    ensure_can_supervise,
)
from internflow_api.domain.exceptions import ReportAlreadySubmittedError, ReportNotFoundError
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.report import IsoWeek, ReportId, WeeklyReport
from internflow_api.domain.user import Principal


@dataclass(frozen=True, slots=True)
class SubmitReportCommand:
    internship_id: InternshipId
    week: IsoWeek
    accomplishments: str
    difficulties: str = ""
    next_steps: str = ""


class SubmitReport:
    """Le stagiaire dépose son rapport de la semaine (un seul par semaine)."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, command: SubmitReportCommand) -> WeeklyReport:
        with self._uow as uow:
            internship = load_visible_internship(uow, actor, command.internship_id)
            ensure_can_submit_report(actor, internship)
            if uow.reports.exists_for_week(internship.id, command.week):
                raise ReportAlreadySubmittedError(command.week)
            report = WeeklyReport.submit(
                internship=internship,
                week=command.week,
                accomplishments=command.accomplishments,
                difficulties=command.difficulties,
                next_steps=command.next_steps,
                now=self._clock.now(),
            )
            uow.reports.add(report)
            uow.commit()
        return report


class ListReports:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, actor: Principal, internship_id: InternshipId) -> Sequence[WeeklyReport]:
        with self._uow as uow:
            load_visible_internship(uow, actor, internship_id)
            return uow.reports.list_for_internship(internship_id)


class ReviewReport:
    """L'encadrant (ou un RH) relit le rapport et laisse un retour."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, report_id: ReportId, feedback: str) -> WeeklyReport:
        with self._uow as uow:
            report = uow.reports.get(report_id)
            internship = uow.internships.get(report.internship_id) if report else None
            if report is None or internship is None or not can_view_internship(actor, internship):
                raise ReportNotFoundError(report_id)
            ensure_can_supervise(actor, internship)
            report.review(feedback, self._clock.now())
            uow.reports.save(report)
            uow.commit()
        return report
