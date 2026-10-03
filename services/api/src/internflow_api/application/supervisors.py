"""Cas d'usage liés aux encadrants."""

from __future__ import annotations

from dataclasses import dataclass

from internflow_api.application.pagination import clamp_pagination
from internflow_api.domain.exceptions import EmailAlreadyUsedError, SupervisorNotFoundError
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.supervisor import DEFAULT_MAX_INTERNS, Supervisor, SupervisorId
from internflow_api.domain.value_objects import Email, PersonName


@dataclass(frozen=True, slots=True)
class RegisterSupervisorCommand:
    first_name: str
    last_name: str
    email: str
    department: str
    max_interns: int = DEFAULT_MAX_INTERNS


class RegisterSupervisor:
    """Enregistre un encadrant. Règle métier : e-mail unique parmi les encadrants."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: RegisterSupervisorCommand) -> Supervisor:
        email = Email(command.email)
        supervisor = Supervisor(
            name=PersonName(command.first_name, command.last_name),
            email=email,
            department=command.department,
            max_interns=command.max_interns,
            created_at=self._clock.now(),
        )
        with self._uow as uow:
            if uow.supervisors.get_by_email(email) is not None:
                raise EmailAlreadyUsedError(email.value)
            uow.supervisors.add(supervisor)
            uow.commit()
        return supervisor


class GetSupervisor:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, supervisor_id: SupervisorId) -> Supervisor:
        with self._uow as uow:
            supervisor = uow.supervisors.get(supervisor_id)
        if supervisor is None:
            raise SupervisorNotFoundError(supervisor_id)
        return supervisor


class ListSupervisors:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, offset: int = 0, limit: int = 20) -> Page[Supervisor]:
        offset, limit = clamp_pagination(offset, limit)
        with self._uow as uow:
            return uow.supervisors.list(offset=offset, limit=limit)
