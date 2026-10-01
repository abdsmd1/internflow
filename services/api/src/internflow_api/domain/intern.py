"""Entité `Intern` (stagiaire).

Une entité a une identité stable (son `id`) : deux stagiaires avec les mêmes
données mais des identifiants différents restent deux personnes distinctes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import InvalidValueError
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel

InternId = NewType("InternId", UUID)

_SCHOOL_MAX_LENGTH = 150


def new_intern_id() -> InternId:
    return InternId(uuid4())


@dataclass(eq=False, slots=True)
class Intern:
    name: PersonName
    email: Email
    school: str
    study_level: StudyLevel
    created_at: datetime
    id: InternId = field(default_factory=new_intern_id)

    def __post_init__(self) -> None:
        self.school = self.school.strip()
        if not self.school:
            raise InvalidValueError("L'établissement d'origine est obligatoire.")
        if len(self.school) > _SCHOOL_MAX_LENGTH:
            raise InvalidValueError(f"L'établissement dépasse {_SCHOOL_MAX_LENGTH} caractères.")
        if self.created_at.tzinfo is None:
            raise InvalidValueError("La date de création doit porter un fuseau horaire.")
        # Invariant : le domaine raisonne toujours en UTC (l'affichage local est
        # l'affaire du frontend), quel que soit le fuseau renvoyé par la base.
        self.created_at = self.created_at.astimezone(UTC)

    # Égalité par identité, comme toute entité.
    def __eq__(self, other: object) -> bool:
        return isinstance(other, Intern) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def change_email(self, new_email: Email) -> None:
        """Comportement métier explicite plutôt qu'un setter anonyme."""
        self.email = new_email
