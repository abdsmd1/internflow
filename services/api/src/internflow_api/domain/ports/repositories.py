from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId, InternshipStatus
from internflow_api.domain.ports.search import Vector
from internflow_api.domain.report import IsoWeek, ReportId, WeeklyReport
from internflow_api.domain.report_search import ReportPassage, SearchHit
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.task import Task, TaskId
from internflow_api.domain.user import User
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


class UserRepository(Protocol):
    def add(self, user: User) -> None: ...

    def get_by_email(self, email: Email) -> User | None: ...

    def exists_for_profile(
        self, *, intern_id: InternId | None = None, supervisor_id: SupervisorId | None = None
    ) -> bool:
        """Un compte est-il déjà rattaché à ce profil stagiaire / encadrant ?"""
        ...


class TaskRepository(Protocol):
    def add(self, task: Task) -> None: ...

    def get(self, task_id: TaskId) -> Task | None: ...

    def save(self, task: Task) -> None: ...

    def list_for_internship(self, internship_id: InternshipId) -> Sequence[Task]:
        """Tâches d'un stage, par échéance croissante."""
        ...


class WeeklyReportRepository(Protocol):
    def add(self, report: WeeklyReport) -> None: ...

    def get(self, report_id: ReportId) -> WeeklyReport | None: ...

    def save(self, report: WeeklyReport) -> None: ...

    def exists_for_week(self, internship_id: InternshipId, week: IsoWeek) -> bool: ...

    def list_for_internship(self, internship_id: InternshipId) -> Sequence[WeeklyReport]:
        """Rapports d'un stage, de la semaine la plus récente à la plus ancienne."""
        ...

    def list_ids(self) -> Sequence[ReportId]:
        """Identifiants de tous les rapports (réindexation complète)."""
        ...


@dataclass(frozen=True, slots=True)
class IndexedPassage:
    passage: ReportPassage
    embedding: Vector
    model: str  # nom du modèle qui a produit le vecteur


class ReportPassageRepository(Protocol):
    """Index de recherche des rapports : passages et vecteurs."""

    def replace_for_report(self, report_id: ReportId, passages: Sequence[IndexedPassage]) -> None:
        """Remplace tous les passages d'un rapport (indexation idempotente)."""
        ...

    def search(
        self,
        query: Vector,
        scope: InternshipFilter,
        *,
        internship_id: InternshipId | None,
        limit: int,
        min_score: float,
    ) -> Sequence[SearchHit]:
        """Passages les plus proches de la question, limités aux stages de `scope`.

        Triés par score décroissant ; ceux sous `min_score` sont écartés.
        """
        ...
