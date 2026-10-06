"""DTO HTTP des tâches."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from internflow_api.application.tasks import TaskOverview
from internflow_api.domain.task import TaskStatus


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=150, examples=["Modéliser le schéma de données"])
    description: str = Field(default="", max_length=2000)
    due_date: date = Field(examples=["2026-10-30"])


class TaskRead(BaseModel):
    id: UUID
    internship_id: UUID
    title: str
    description: str
    due_date: date
    status: TaskStatus
    is_overdue: bool = Field(description="Échéance dépassée et tâche non terminée.")
    created_by: UUID
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_overview(cls, overview: TaskOverview) -> TaskRead:
        task = overview.task
        return cls(
            id=task.id,
            internship_id=task.internship_id,
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            status=task.status,
            is_overdue=overview.is_overdue,
            created_by=task.created_by,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )
