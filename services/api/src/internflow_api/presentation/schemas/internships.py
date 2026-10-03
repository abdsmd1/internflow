"""DTO HTTP des stages."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from internflow_api.domain.internship import Internship, InternshipStatus
from internflow_api.domain.ports.repositories import Page


class InternshipCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    intern_id: UUID
    supervisor_id: UUID
    subject: str = Field(
        min_length=1, max_length=200, examples=["Agent IA de suivi des stagiaires"]
    )
    start_date: date = Field(examples=["2026-11-02"])
    end_date: date = Field(examples=["2027-03-31"])


class InternshipRead(BaseModel):
    id: UUID
    intern_id: UUID
    supervisor_id: UUID
    subject: str
    start_date: date
    end_date: date
    duration_days: int = Field(description="Durée en jours, bornes incluses.")
    status: InternshipStatus
    created_at: datetime

    @classmethod
    def from_entity(cls, internship: Internship) -> InternshipRead:
        return cls(
            id=internship.id,
            intern_id=internship.intern_id,
            supervisor_id=internship.supervisor_id,
            subject=internship.subject,
            start_date=internship.period.start,
            end_date=internship.period.end,
            duration_days=internship.period.days,
            status=internship.status,
            created_at=internship.created_at,
        )


class InternshipPage(BaseModel):
    items: list[InternshipRead]
    total: int
    offset: int
    limit: int

    @classmethod
    def from_page(cls, page: Page[Internship]) -> InternshipPage:
        return cls(
            items=[InternshipRead.from_entity(i) for i in page.items],
            total=page.total,
            offset=page.offset,
            limit=page.limit,
        )
