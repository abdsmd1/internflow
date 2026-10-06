"""Entité `WeeklyReport` (rapport hebdomadaire) et value object `IsoWeek`.

Une semaine est identifiée selon la norme ISO 8601 (« 2026-W41 ») : du lundi au
dimanche, sans ambiguïté autour du changement d'année. Un stage a au plus un
rapport par semaine.

Cycle de vie : SUBMITTED ──review──▶ REVIEWED (avec le retour de l'encadrant).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import (
    InternshipNotOngoingError,
    InvalidStatusTransitionError,
    InvalidValueError,
)
from internflow_api.domain.internship import Internship, InternshipId, InternshipStatus

ReportId = NewType("ReportId", UUID)

_TEXT_MAX_LENGTH = 5000
_FEEDBACK_MAX_LENGTH = 2000
_ISO_WEEK_PATTERN = re.compile(r"^(\d{4})-W(\d{2})$")


def new_report_id() -> ReportId:
    return ReportId(uuid4())


@dataclass(frozen=True, slots=True, order=True)
class IsoWeek:
    year: int
    week: int

    def __post_init__(self) -> None:
        try:
            date.fromisocalendar(self.year, self.week, 1)
        except ValueError as exc:
            raise InvalidValueError(
                f"Semaine ISO invalide : {self.year}-W{self.week:02d}."
            ) from exc

    @classmethod
    def of(cls, day: date) -> IsoWeek:
        iso = day.isocalendar()
        return cls(iso.year, iso.week)

    @classmethod
    def parse(cls, text: str) -> IsoWeek:
        match = _ISO_WEEK_PATTERN.match(text.strip())
        if match is None:
            raise InvalidValueError(
                f"Format de semaine attendu : AAAA-Wss (ex. 2026-W41), reçu {text!r}."
            )
        return cls(int(match.group(1)), int(match.group(2)))

    @property
    def monday(self) -> date:
        return date.fromisocalendar(self.year, self.week, 1)

    @property
    def sunday(self) -> date:
        return self.monday + timedelta(days=6)

    def __str__(self) -> str:
        return f"{self.year}-W{self.week:02d}"


class ReportStatus(StrEnum):
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


def _bounded(text: str, label: str, max_length: int, *, required: bool = False) -> str:
    text = text.strip()
    if required and not text:
        raise InvalidValueError(f"Le champ « {label} » est obligatoire.")
    if len(text) > max_length:
        raise InvalidValueError(f"Le champ « {label} » dépasse {max_length} caractères.")
    return text


def _utc(moment: datetime, label: str) -> datetime:
    if moment.tzinfo is None:
        raise InvalidValueError(f"La date « {label} » doit porter un fuseau horaire.")
    return moment.astimezone(UTC)


@dataclass(eq=False, slots=True)
class WeeklyReport:
    internship_id: InternshipId
    week: IsoWeek
    accomplishments: str
    submitted_at: datetime
    difficulties: str = ""
    next_steps: str = ""
    status: ReportStatus = ReportStatus.SUBMITTED
    feedback: str | None = None
    reviewed_at: datetime | None = None
    id: ReportId = field(default_factory=new_report_id)

    def __post_init__(self) -> None:
        self.accomplishments = _bounded(
            self.accomplishments, "réalisations", _TEXT_MAX_LENGTH, required=True
        )
        self.difficulties = _bounded(self.difficulties, "difficultés", _TEXT_MAX_LENGTH)
        self.next_steps = _bounded(self.next_steps, "prochaines étapes", _TEXT_MAX_LENGTH)
        self.submitted_at = _utc(self.submitted_at, "dépôt")
        if self.reviewed_at is not None:
            self.reviewed_at = _utc(self.reviewed_at, "relecture")
        reviewed = self.status is ReportStatus.REVIEWED
        if reviewed != (self.feedback is not None and self.reviewed_at is not None):
            raise InvalidValueError("Un rapport relu, et seulement lui, a un retour et une date.")

    @classmethod
    def submit(
        cls,
        *,
        internship: Internship,
        week: IsoWeek,
        accomplishments: str,
        now: datetime,
        difficulties: str = "",
        next_steps: str = "",
    ) -> WeeklyReport:
        """Règles : stage en cours, semaine dans la période du stage et déjà commencée."""
        if internship.status is not InternshipStatus.ONGOING:
            raise InternshipNotOngoingError(internship.id)
        if week.sunday < internship.period.start or week.monday > internship.period.end:
            raise InvalidValueError(f"La semaine {week} est en dehors de la période du stage.")
        if week.monday > now.astimezone(UTC).date():
            raise InvalidValueError(f"La semaine {week} n'a pas encore commencé.")
        return cls(
            internship_id=internship.id,
            week=week,
            accomplishments=accomplishments,
            difficulties=difficulties,
            next_steps=next_steps,
            submitted_at=now,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, WeeklyReport) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def review(self, feedback: str, now: datetime) -> None:
        if self.status is not ReportStatus.SUBMITTED:
            raise InvalidStatusTransitionError(self.status.value, "relire")
        self.feedback = _bounded(feedback, "retour", _FEEDBACK_MAX_LENGTH, required=True)
        self.reviewed_at = _utc(now, "relecture")
        self.status = ReportStatus.REVIEWED
