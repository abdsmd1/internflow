"""Cas d'usage liés aux stages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date
from enum import StrEnum

from internflow_api.application.pagination import clamp_pagination
from internflow_api.domain.authorization import (
    ensure_can_cancel_internship,
    ensure_can_progress_internship,
    ensure_can_view_internship,
    require_role,
    scope_internship_filter,
)
from internflow_api.domain.exceptions import (
    InternNotFoundError,
    InternshipNotFoundError,
    InternshipOverlapError,
    SupervisorNotFoundError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.repositories import InternshipFilter, Page
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.user import Principal, Role


@dataclass(frozen=True, slots=True)
class PlanInternshipCommand:
    intern_id: InternId
    supervisor_id: SupervisorId
    subject: str
    start_date: date
    end_date: date


class PlanInternship:
    """Planifie un stage (RH) en vérifiant les règles qui dépendent de l'existant.

    1. le stagiaire et l'encadrant existent ;
    2. le stagiaire n'a pas déjà un stage actif sur la période ;
    3. l'encadrant n'a pas atteint sa capacité sur la période.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, command: PlanInternshipCommand) -> Internship:
        require_role(actor, Role.HR)
        period = DateRange(command.start_date, command.end_date)
        with self._uow as uow:
            if uow.interns.get(command.intern_id) is None:
                raise InternNotFoundError(command.intern_id)
            # Verrou sur l'encadrant : les affectations concurrentes sont sérialisées.
            supervisor = uow.supervisors.get(command.supervisor_id, for_update=True)
            if supervisor is None:
                raise SupervisorNotFoundError(command.supervisor_id)

            internship = Internship.plan(
                intern_id=command.intern_id,
                supervisor_id=command.supervisor_id,
                subject=command.subject,
                period=period,
                now=self._clock.now(),
            )
            if uow.internships.has_active_overlap(command.intern_id, period):
                raise InternshipOverlapError(command.intern_id)
            supervisor.ensure_can_supervise_one_more(
                uow.internships.count_active_overlapping_for_supervisor(supervisor.id, period)
            )

            uow.internships.add(internship)
            uow.commit()
        return internship


class GetInternship:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, actor: Principal, internship_id: InternshipId) -> Internship:
        with self._uow as uow:
            internship = uow.internships.get(internship_id)
        if internship is None:
            raise InternshipNotFoundError(internship_id)
        ensure_can_view_internship(actor, internship)
        return internship


class ListInternships:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(
        self,
        actor: Principal,
        criteria: InternshipFilter | None = None,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Page[Internship]:
        offset, limit = clamp_pagination(offset, limit)
        scoped = scope_internship_filter(actor, criteria or InternshipFilter())
        with self._uow as uow:
            return uow.internships.list(scoped, offset=offset, limit=limit)


class InternshipAction(StrEnum):
    START = "start"
    COMPLETE = "complete"
    CANCEL = "cancel"


class ChangeInternshipStatus:
    """Fait avancer un stage dans son cycle de vie.

    Le cas d'usage ne décide de rien : c'est l'entité qui accepte ou refuse la transition.
    """

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(
        self, actor: Principal, internship_id: InternshipId, action: InternshipAction
    ) -> Internship:
        with self._uow as uow:
            internship = uow.internships.get(internship_id)
            if internship is None:
                raise InternshipNotFoundError(internship_id)
            if action is InternshipAction.CANCEL:
                ensure_can_cancel_internship(actor, internship)
            else:
                ensure_can_progress_internship(actor, internship)
            match action:
                case InternshipAction.START:
                    internship.start(today=self._clock.now().astimezone(UTC).date())
                case InternshipAction.COMPLETE:
                    internship.complete()
                case InternshipAction.CANCEL:
                    internship.cancel()
            uow.internships.save(internship)
            uow.commit()
        return internship
