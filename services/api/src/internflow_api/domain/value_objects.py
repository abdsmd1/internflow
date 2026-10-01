"""Value objects : objets immuables, comparés par valeur, toujours valides.

Un value object valide ses invariants à la construction : il est impossible
de manipuler un `Email` mal formé ailleurs dans le code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from internflow_api.domain.exceptions import InvalidValueError

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_NAME_MAX_LENGTH = 100
_EMAIL_MAX_LENGTH = 254  # RFC 5321


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > _EMAIL_MAX_LENGTH or not _EMAIL_PATTERN.match(normalized):
            raise InvalidValueError(f"Adresse e-mail invalide : {self.value!r}.")
        # frozen=True interdit l'affectation directe : on passe par object.__setattr__.
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PersonName:
    first_name: str
    last_name: str

    def __post_init__(self) -> None:
        first, last = self.first_name.strip(), self.last_name.strip()
        for label, part in (("prénom", first), ("nom", last)):
            if not part:
                raise InvalidValueError(f"Le {label} est obligatoire.")
            if len(part) > _NAME_MAX_LENGTH:
                raise InvalidValueError(f"Le {label} dépasse {_NAME_MAX_LENGTH} caractères.")
        object.__setattr__(self, "first_name", first)
        object.__setattr__(self, "last_name", last)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class StudyLevel(StrEnum):
    """Niveau d'études du stagiaire (système LMD + cycle ingénieur)."""

    BAC_PLUS_2 = "bac+2"
    LICENCE = "licence"
    MASTER_1 = "master_1"
    MASTER_2 = "master_2"
    INGENIEUR = "ingenieur"
    DOCTORAT = "doctorat"
