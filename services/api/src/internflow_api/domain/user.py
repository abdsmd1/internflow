"""Comptes utilisateurs, rôles et identité de l'appelant.

- `User` : le compte stocké (e-mail, empreinte du mot de passe, rôle, profil lié).
- `Principal` : « qui appelle ? » — l'identité authentifiée transmise aux cas d'usage.

Un compte est rattaché au profil métier correspondant à son rôle :
un encadrant à un `Supervisor`, un stagiaire à un `Intern`, un RH à aucun profil.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import NewType
from uuid import UUID, uuid4

from internflow_api.domain.exceptions import InvalidValueError
from internflow_api.domain.intern import InternId
from internflow_api.domain.supervisor import SupervisorId
from internflow_api.domain.value_objects import Email

UserId = NewType("UserId", UUID)


def new_user_id() -> UserId:
    return UserId(uuid4())


class Role(StrEnum):
    HR = "hr"
    SUPERVISOR = "supervisor"
    INTERN = "intern"


@dataclass(frozen=True, slots=True)
class Principal:
    """Identité authentifiée de l'appelant, immuable."""

    user_id: UserId
    role: Role
    intern_id: InternId | None = None
    supervisor_id: SupervisorId | None = None


@dataclass(eq=False, slots=True)
class User:
    email: Email
    password_hash: str
    role: Role
    created_at: datetime
    intern_id: InternId | None = None
    supervisor_id: SupervisorId | None = None
    is_active: bool = True
    id: UserId = field(default_factory=new_user_id)

    def __post_init__(self) -> None:
        if not self.password_hash:
            raise InvalidValueError("L'empreinte du mot de passe est obligatoire.")
        expected = {
            Role.HR: (False, False),
            Role.SUPERVISOR: (False, True),
            Role.INTERN: (True, False),
        }[self.role]
        if (self.intern_id is not None, self.supervisor_id is not None) != expected:
            raise InvalidValueError(
                "Profil incohérent avec le rôle : un stagiaire est lié à un stagiaire, "
                "un encadrant à un encadrant, un RH à aucun profil."
            )
        if self.created_at.tzinfo is None:
            raise InvalidValueError("La date de création doit porter un fuseau horaire.")
        self.created_at = self.created_at.astimezone(UTC)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, User) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)

    def to_principal(self) -> Principal:
        return Principal(
            user_id=self.id,
            role=self.role,
            intern_id=self.intern_id,
            supervisor_id=self.supervisor_id,
        )
