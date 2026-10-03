"""DTO HTTP des encadrants."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.supervisor import (
    DEFAULT_MAX_INTERNS,
    MAX_INTERNS_UPPER_BOUND,
    Supervisor,
)


class SupervisorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100, examples=["Karim"])
    last_name: str = Field(min_length=1, max_length=100, examples=["Benali"])
    email: EmailStr = Field(examples=["karim.benali@example.com"])
    department: str = Field(min_length=1, max_length=100, examples=["Data & IA"])
    max_interns: int = Field(
        default=DEFAULT_MAX_INTERNS,
        ge=1,
        le=MAX_INTERNS_UPPER_BOUND,
        description="Nombre maximal de stagiaires suivis en même temps.",
    )


class SupervisorRead(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    department: str
    max_interns: int
    created_at: datetime

    @classmethod
    def from_entity(cls, supervisor: Supervisor) -> SupervisorRead:
        return cls(
            id=supervisor.id,
            first_name=supervisor.name.first_name,
            last_name=supervisor.name.last_name,
            email=supervisor.email.value,
            department=supervisor.department,
            max_interns=supervisor.max_interns,
            created_at=supervisor.created_at,
        )


class SupervisorPage(BaseModel):
    items: list[SupervisorRead]
    total: int
    offset: int
    limit: int

    @classmethod
    def from_page(cls, page: Page[Supervisor]) -> SupervisorPage:
        return cls(
            items=[SupervisorRead.from_entity(s) for s in page.items],
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )
