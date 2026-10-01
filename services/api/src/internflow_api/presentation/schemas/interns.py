"""DTO HTTP (Pydantic). Ils définissent le contrat public de l'API.

Ils sont distincts des entités : on peut faire évoluer le domaine sans casser
les clients, et on n'expose jamais un champ interne par accident.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from internflow_api.domain.intern import Intern
from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.value_objects import StudyLevel


class InternCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100, examples=["Sara"])
    last_name: str = Field(min_length=1, max_length=100, examples=["El Amrani"])
    email: EmailStr = Field(examples=["sara.elamrani@example.com"])
    school: str = Field(min_length=1, max_length=150, examples=["ENSA Oujda"])
    study_level: StudyLevel = Field(examples=[StudyLevel.INGENIEUR])


class InternRead(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: str
    school: str
    study_level: StudyLevel
    created_at: datetime

    @classmethod
    def from_entity(cls, intern: Intern) -> InternRead:
        return cls(
            id=intern.id,
            first_name=intern.name.first_name,
            last_name=intern.name.last_name,
            email=intern.email.value,
            school=intern.school,
            study_level=intern.study_level,
            created_at=intern.created_at,
        )


class InternPage(BaseModel):
    items: list[InternRead]
    total: int
    offset: int
    limit: int

    @classmethod
    def from_page(cls, page: Page[Intern]) -> InternPage:
        return cls(
            items=[InternRead.from_entity(i) for i in page.items],
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )
