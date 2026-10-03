"""Cas d'usage liés aux stagiaires."""

from __future__ import annotations

from dataclasses import dataclass

from internflow_api.application.pagination import clamp_pagination
from internflow_api.domain.exceptions import EmailAlreadyUsedError, InternNotFoundError
from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel


@dataclass(frozen=True, slots=True)
class RegisterInternCommand:
    """Données d'entrée du cas d'usage (types primitifs, sans framework)."""

    first_name: str
    last_name: str
    email: str
    school: str
    study_level: StudyLevel


class RegisterIntern:
    """Inscrit un nouveau stagiaire. Règle métier : e-mail unique."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, command: RegisterInternCommand) -> Intern:
        email = Email(command.email)
        intern = Intern(
            name=PersonName(command.first_name, command.last_name),
            email=email,
            school=command.school,
            study_level=command.study_level,
            created_at=self._clock.now(),
        )
        with self._uow as uow:
            if uow.interns.get_by_email(email) is not None:
                raise EmailAlreadyUsedError(email.value)
            uow.interns.add(intern)
            uow.commit()
        return intern


class GetIntern:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, intern_id: InternId) -> Intern:
        with self._uow as uow:
            intern = uow.interns.get(intern_id)
        if intern is None:
            raise InternNotFoundError(intern_id)
        return intern


class ListInterns:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, offset: int = 0, limit: int = 20) -> Page[Intern]:
        offset, limit = clamp_pagination(offset, limit)
        with self._uow as uow:
            return uow.interns.list(offset=offset, limit=limit)
