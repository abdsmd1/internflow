from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.value_objects import Email


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Résultat paginé, indépendant de toute technologie."""

    items: Sequence[T]
    total: int
    offset: int
    limit: int


class InternRepository(Protocol):
    """Collection persistante de stagiaires (pattern Repository)."""

    def add(self, intern: Intern) -> None: ...

    def get(self, intern_id: InternId) -> Intern | None: ...

    def get_by_email(self, email: Email) -> Intern | None: ...

    def list(self, *, offset: int, limit: int) -> Page[Intern]: ...
