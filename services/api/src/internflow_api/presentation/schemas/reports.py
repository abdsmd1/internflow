"""DTO HTTP des rapports hebdomadaires."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from internflow_api.domain.report import ReportStatus, WeeklyReport

ISO_WEEK_PATTERN = r"^\d{4}-W\d{2}$"


class ReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    week: str = Field(
        pattern=ISO_WEEK_PATTERN,
        description="Semaine ISO 8601, du lundi au dimanche.",
        examples=["2026-W41"],
    )
    accomplishments: str = Field(
        min_length=1, max_length=5000, examples=["Mise en place du pipeline d'ingestion."]
    )
    difficulties: str = Field(default="", max_length=5000)
    next_steps: str = Field(default="", max_length=5000)


class ReportReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    feedback: str = Field(
        min_length=1, max_length=2000, examples=["Bon avancement, documenter le schéma."]
    )


class ReportRead(BaseModel):
    id: UUID
    internship_id: UUID
    week: str
    week_start: date
    week_end: date
    accomplishments: str
    difficulties: str
    next_steps: str
    status: ReportStatus
    feedback: str | None
    submitted_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_entity(cls, report: WeeklyReport) -> ReportRead:
        return cls(
            id=report.id,
            internship_id=report.internship_id,
            week=str(report.week),
            week_start=report.week.monday,
            week_end=report.week.sunday,
            accomplishments=report.accomplishments,
            difficulties=report.difficulties,
            next_steps=report.next_steps,
            status=report.status,
            feedback=report.feedback,
            submitted_at=report.submitted_at,
            reviewed_at=report.reviewed_at,
        )
