"""Entité `Supervisor` (encadrant) : la personne qui suit un ou plusieurs stagiaires."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import InvalidValueError, SupervisorCapacityExceededError
from internflow_api.domain.value_objects import Email, PersonName

SupervisorId = NewType("SupervisorId", UUID)

DEFAULT_MAX_INTERNS = 5
MAX_INTERNS_UPPER_BOUND = 10
_DEPARTMENT_MAX_LENGTH = 100


def new_supervisor_id() -> SupervisorId:
    return SupervisorId(uuid4())


@dataclass(eq=False, slots=True)
class Supervisor:
    name: PersonName
    email: Email
    department: str
    created_at: datetime
    max_interns: int = DEFAULT_MAX_INTERNS
    id: SupervisorId = field(default_factory=new_supervisor_id)

    def __post_init__(self) -> None:
        self.department = self.department.strip()
        if not self.department:
            raise InvalidValueError("Le département est obligatoire.")
        if len(self.department) > _DEPARTMENT_MAX_LENGTH:
            raise InvalidValueError(f"Le département dépasse {_DEPARTMENT_MAX_LENGTH} caractères.")
        if not 1 <= self.max_interns <= MAX_INTERNS_UPPER_BOUND:
            raise InvalidValueError(
                "La capacité d'encadrement doit être comprise entre 1 et "
                f"{MAX_INTERNS_UPPER_BOUND}."
            )
        if self.created_at.tzinfo is None:
            raise InvalidValueError("La date de création doit porter un fuseau horaire.")
        self.created_at = self.created_at.astimezone(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Supervisor) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def ensure_can_supervise_one_more(self, current_load: int) -> None:
        """Règle métier : un encadrant ne dépasse jamais sa capacité.

        `current_load` = nombre de stages actifs qui chevauchent la période visée
        (estimation volontairement prudente, voir ADR 0006).
        """
        if current_load >= self.max_interns:
            raise SupervisorCapacityExceededError(self.id, self.max_interns)
