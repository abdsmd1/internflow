"""Cas d'usage liés aux tâches."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date
from enum import StrEnum

from internflow_api.application.internships import load_visible_internship
from internflow_api.domain.authorization import (
    can_view_internship,
    ensure_can_supervise,
)
from internflow_api.domain.exceptions import InternshipClosedError, TaskNotFoundError
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.ports.clock import Clock
from internflow_api.domain.ports.unit_of_work import UnitOfWork
from internflow_api.domain.task import Task, TaskId
from internflow_api.domain.user import Principal


@dataclass(frozen=True, slots=True)
class TaskOverview:
    """Une tâche et son retard éventuel, calculé à la date du jour."""

    task: Task
    is_overdue: bool

    @classmethod
    def of(cls, task: Task, today: date) -> TaskOverview:
        return cls(task=task, is_overdue=task.is_overdue(today))


def _today(clock: Clock) -> date:
    return clock.now().astimezone(UTC).date()


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    internship_id: InternshipId
    title: str
    due_date: date
    description: str = ""


class CreateTask:
    """L'encadrant (ou un RH) confie une tâche au stagiaire."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, command: CreateTaskCommand) -> TaskOverview:
        now = self._clock.now()
        with self._uow as uow:
            internship = load_visible_internship(uow, actor, command.internship_id)
            ensure_can_supervise(actor, internship)
            task = Task.create(
                internship=internship,
                title=command.title,
                description=command.description,
                due_date=command.due_date,
                created_by=actor.user_id,
                now=now,
            )
            uow.tasks.add(task)
            uow.commit()
        return TaskOverview.of(task, now.astimezone(UTC).date())


class ListTasks:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, internship_id: InternshipId) -> Sequence[TaskOverview]:
        today = _today(self._clock)
        with self._uow as uow:
            load_visible_internship(uow, actor, internship_id)
            tasks = uow.tasks.list_for_internship(internship_id)
        return [TaskOverview.of(t, today) for t in tasks]


class TaskAction(StrEnum):
    START = "start"
    COMPLETE = "complete"


class ChangeTaskStatus:
    """Toute personne qui voit le stage (stagiaire, encadrant, RH) fait avancer ses tâches."""

    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def execute(self, actor: Principal, task_id: TaskId, action: TaskAction) -> TaskOverview:
        now = self._clock.now()
        with self._uow as uow:
            task = uow.tasks.get(task_id)
            internship = uow.internships.get(task.internship_id) if task else None
            # Une tâche d'un stage invisible pour l'appelant est « introuvable ».
            if task is None or internship is None or not can_view_internship(actor, internship):
                raise TaskNotFoundError(task_id)
            if not internship.is_active:
                raise InternshipClosedError(internship.id)
            match action:
                case TaskAction.START:
                    task.start()
                case TaskAction.COMPLETE:
                    task.complete(now)
            uow.tasks.save(task)
            uow.commit()
        return TaskOverview.of(task, now.astimezone(UTC).date())
