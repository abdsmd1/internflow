"""Routes des tâches : rattachées à un stage, puis manipulées par leur identifiant."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from internflow_api.application.tasks import (
    ChangeTaskStatus,
    CreateTask,
    CreateTaskCommand,
    ListTasks,
    TaskAction,
)
from internflow_api.domain.internship import InternshipId
from internflow_api.domain.task import TaskId
from internflow_api.presentation.dependencies import (
    change_task_status_use_case,
    create_task_use_case,
    list_tasks_use_case,
)
from internflow_api.presentation.schemas.tasks import TaskCreate, TaskRead
from internflow_api.presentation.security import ActorDep

router = APIRouter(tags=["Tâches"])

ChangeTaskDep = Annotated[ChangeTaskStatus, Depends(change_task_status_use_case)]
_TRANSITION_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {"description": "Tâche introuvable"},
    status.HTTP_409_CONFLICT: {"description": "Transition refusée ou stage clôturé"},
}


@router.post(
    "/internships/{internship_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    summary="Confier une tâche (encadrant du stage ou RH)",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable"},
        status.HTTP_409_CONFLICT: {"description": "Stage terminé ou annulé"},
    },
)
def create_task(
    internship_id: UUID,
    payload: TaskCreate,
    actor: ActorDep,
    use_case: Annotated[CreateTask, Depends(create_task_use_case)],
) -> TaskRead:
    overview = use_case.execute(
        actor,
        CreateTaskCommand(
            internship_id=InternshipId(internship_id),
            title=payload.title,
            description=payload.description,
            due_date=payload.due_date,
        ),
    )
    return TaskRead.from_overview(overview)


@router.get(
    "/internships/{internship_id}/tasks",
    summary="Lister les tâches d'un stage (par échéance)",
    responses={status.HTTP_404_NOT_FOUND: {"description": "Stage introuvable"}},
)
def list_tasks(
    internship_id: UUID,
    actor: ActorDep,
    use_case: Annotated[ListTasks, Depends(list_tasks_use_case)],
) -> list[TaskRead]:
    return [TaskRead.from_overview(o) for o in use_case.execute(actor, InternshipId(internship_id))]


@router.post(
    "/tasks/{task_id}/start", summary="Commencer une tâche", responses=_TRANSITION_RESPONSES
)
def start_task(task_id: UUID, actor: ActorDep, use_case: ChangeTaskDep) -> TaskRead:
    return TaskRead.from_overview(use_case.execute(actor, TaskId(task_id), TaskAction.START))


@router.post(
    "/tasks/{task_id}/complete", summary="Terminer une tâche", responses=_TRANSITION_RESPONSES
)
def complete_task(task_id: UUID, actor: ActorDep, use_case: ChangeTaskDep) -> TaskRead:
    return TaskRead.from_overview(use_case.execute(actor, TaskId(task_id), TaskAction.COMPLETE))
