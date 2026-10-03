"""Entité `Internship` (stage) : relie un stagiaire, un encadrant et une période.

Le cycle de vie d'un stage est une **machine à états** :

    PLANNED ──start──▶ ONGOING ──complete──▶ COMPLETED
       │                  │
       └──────cancel──────┴──▶ CANCELLED

Toute autre transition est refusée par l'entité elle-même.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import (
    InternshipNotStartableYetError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId

InternshipId = NewType("InternshipId", UUID)

MAX_INTERNSHIP_DAYS = 183  # ≈ 6 mois : durée maximale d'un stage (PFE compris)
_SUBJECT_MAX_LENGTH = 200


def new_internship_id() -> InternshipId:
    return InternshipId(uuid4())


class InternshipStatus(StrEnum):
    PLANNED = "planned"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Un stage « actif » occupe le stagiaire et l'encadrant sur sa période.
ACTIVE_STATUSES: frozenset[InternshipStatus] = frozenset(
    {InternshipStatus.PLANNED, InternshipStatus.ONGOING}
)


@dataclass(frozen=True, slots=True)
class DateRange:
    """Période de dates inclusive [start, end] — value object."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InvalidValueError("La date de fin doit être postérieure à la date de début.")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def overlaps(self, other: DateRange) -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(eq=False, slots=True)
class Internship:
    intern_id: InternId
    supervisor_id: SupervisorId
    subject: str
    period: DateRange
    created_at: datetime
    status: InternshipStatus = InternshipStatus.PLANNED
    id: InternshipId = field(default_factory=new_internship_id)

    def __post_init__(self) -> None:
        self.subject = self.subject.strip()
        if not self.subject:
            raise InvalidValueError("Le sujet du stage est obligatoire.")
        if len(self.subject) > _SUBJECT_MAX_LENGTH:
            raise InvalidValueError(f"Le sujet dépasse {_SUBJECT_MAX_LENGTH} caractères.")
        if self.period.days > MAX_INTERNSHIP_DAYS:
            raise InvalidValueError(f"Un stage ne peut pas dépasser {MAX_INTERNSHIP_DAYS} jours.")
        if self.created_at.tzinfo is None:
            raise InvalidValueError("La date de création doit porter un fuseau horaire.")
        self.created_at = self.created_at.astimezone(UTC)

    @classmethod
    def plan(
        cls,
        *,
        intern_id: InternId,
        supervisor_id: SupervisorId,
        subject: str,
        period: DateRange,
        now: datetime,
    ) -> Internship:
        """Fabrique : planifier un nouveau stage (règle : il ne peut pas être déjà terminé)."""
        if period.end < now.astimezone(UTC).date():
            raise InvalidValueError(
                "Impossible de planifier un stage dont la date de fin est passée."
            )
        return cls(
            intern_id=intern_id,
            supervisor_id=supervisor_id,
            subject=subject,
            period=period,
            created_at=now,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Internship) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    # ---------------------------------------------------------- transitions
    def start(self, today: date) -> None:
        self._require(InternshipStatus.PLANNED, action="démarrer")
        if today < self.period.start:
            raise InternshipNotStartableYetError(self.period.start)
        self.status = InternshipStatus.ONGOING

    def complete(self) -> None:
        self._require(InternshipStatus.ONGOING, action="terminer")
        self.status = InternshipStatus.COMPLETED

    def cancel(self) -> None:
        self._require(*ACTIVE_STATUSES, action="annuler")
        self.status = InternshipStatus.CANCELLED

    def _require(self, *allowed: InternshipStatus, action: str) -> None:
        if self.status not in allowed:
            raise InvalidStatusTransitionError(self.status.value, action)
