from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId, InternshipStatus
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.value_objects import Email


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Résultat paginé, indépendant de toute technologie."""

    items: Sequence[T]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class InternshipFilter:
    """Critères de recherche de stages (tous facultatifs, combinés par ET)."""

    intern_id: InternId | None = None
    supervisor_id: SupervisorId | None = None
    status: InternshipStatus | None = None


class InternRepository(Protocol):
    """Collection persistante de stagiaires (pattern Repository)."""

    def add(self, intern: Intern) -> None: ...

    def get(self, intern_id: InternId) -> Intern | None: ...

    def get_by_email(self, email: Email) -> Intern | None: ...

    def list(self, *, offset: int, limit: int) -> Page[Intern]: ...


class SupervisorRepository(Protocol):
    def add(self, supervisor: Supervisor) -> None: ...

    def get(self, supervisor_id: SupervisorId, *, for_update: bool = False) -> Supervisor | None:
        """`for_update=True` réserve l'encadrant jusqu'à la fin de la transaction.

        Deux affectations simultanées au même encadrant sont ainsi traitées l'une
        après l'autre : la règle de capacité ne peut pas être contournée.
        """
        ...

    def get_by_email(self, email: Email) -> Supervisor | None: ...

    def list(self, *, offset: int, limit: int) -> Page[Supervisor]: ...


class InternshipRepository(Protocol):
    def add(self, internship: Internship) -> None: ...

    def get(self, internship_id: InternshipId) -> Internship | None: ...

    def save(self, internship: Internship) -> None:
        """Enregistre les changements d'un stage existant (ex. changement de statut)."""
        ...

    def list(self, criteria: InternshipFilter, *, offset: int, limit: int) -> Page[Internship]: ...

    def has_active_overlap(self, intern_id: InternId, period: DateRange) -> bool:
        """Le stagiaire a-t-il déjà un stage actif qui chevauche cette période ?"""
        ...

    def count_active_overlapping_for_supervisor(
        self, supervisor_id: SupervisorId, period: DateRange
    ) -> int: ...
