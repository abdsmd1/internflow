"""Entité `Task` (tâche) : un travail confié au stagiaire dans le cadre de son stage.

Cycle de vie : TODO ──start──▶ IN_PROGRESS ──complete──▶ DONE
                 └────────────complete───────────────▶ DONE

La date de réalisation (`completed_at`) est conservée : elle alimentera les
indicateurs (délais, retards) calculés par les pipelines de données.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import (
    InternshipClosedError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.internship import Internship, InternshipId
from internflow_api.domain.user import UserId

TaskId = NewType("TaskId", UUID)

_TITLE_MAX_LENGTH = 150
_DESCRIPTION_MAX_LENGTH = 2000


def new_task_id() -> TaskId:
    return TaskId(uuid4())


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def _utc(moment: datetime, label: str) -> datetime:
    if moment.tzinfo is None:
        raise InvalidValueError(f"La date « {label} » doit porter un fuseau horaire.")
    return moment.astimezone(UTC)


@dataclass(eq=False, slots=True)
class Task:
    internship_id: InternshipId
    title: str
    due_date: date
    created_by: UserId
    created_at: datetime
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    completed_at: datetime | None = None
    id: TaskId = field(default_factory=new_task_id)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title:
            raise InvalidValueError("Le titre de la tâche est obligatoire.")
        if len(self.title) > _TITLE_MAX_LENGTH:
            raise InvalidValueError(f"Le titre dépasse {_TITLE_MAX_LENGTH} caractères.")
        if len(self.description) > _DESCRIPTION_MAX_LENGTH:
            raise InvalidValueError(f"La description dépasse {_DESCRIPTION_MAX_LENGTH} caractères.")
        self.created_at = _utc(self.created_at, "création")
        if self.completed_at is not None:
            self.completed_at = _utc(self.completed_at, "réalisation")
        if (self.status is TaskStatus.DONE) != (self.completed_at is not None):
            raise InvalidValueError(
                "Une tâche terminée, et seulement elle, a une date de réalisation."
            )

    @classmethod
    def create(
        cls,
        *,
        internship: Internship,
        title: str,
        due_date: date,
        created_by: UserId,
        now: datetime,
        description: str = "",
    ) -> Task:
        """Règles : stage encore actif, échéance comprise dans la période du stage."""
        if not internship.is_active:
            raise InternshipClosedError(internship.id)
        if not internship.period.start <= due_date <= internship.period.end:
            raise InvalidValueError(
                f"L'échéance doit être comprise dans la période du stage "
                f"({internship.period.start} → {internship.period.end})."
            )
        return cls(
            internship_id=internship.id,
            title=title,
            description=description,
            due_date=due_date,
            created_by=created_by,
            created_at=now,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Task) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def is_overdue(self, today: date) -> bool:
        return self.status is not TaskStatus.DONE and self.due_date < today

    def start(self) -> None:
        if self.status is not TaskStatus.TODO:
            raise InvalidStatusTransitionError(self.status.value, "commencer")
        self.status = TaskStatus.IN_PROGRESS

    def complete(self, now: datetime) -> None:
        if self.status is TaskStatus.DONE:
            raise InvalidStatusTransitionError(self.status.value, "terminer")
        self.status = TaskStatus.DONE
        self.completed_at = _utc(now, "réalisation")
