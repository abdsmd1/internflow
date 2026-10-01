"""Adaptateur en mémoire : pour les tests rapides et le prototypage.

Il implémente exactement les mêmes ports que l'adaptateur PostgreSQL.
"""

from __future__ import annotations

import copy
from types import TracebackType
from typing import Self

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.value_objects import Email


class InMemoryInternRepository:
    def __init__(self) -> None:
        self._items: dict[InternId, Intern] = {}

    def add(self, intern: Intern) -> None:
        self._items[intern.id] = copy.deepcopy(intern)

    def get(self, intern_id: InternId) -> Intern | None:
        intern = self._items.get(intern_id)
        return copy.deepcopy(intern) if intern else None

    def get_by_email(self, email: Email) -> Intern | None:
        found = next((i for i in self._items.values() if i.email == email), None)
        return copy.deepcopy(found) if found else None

    def list(self, *, offset: int, limit: int) -> Page[Intern]:
        ordered = sorted(self._items.values(), key=lambda i: (-i.created_at.timestamp(), i.id))
        return Page(
            items=[copy.deepcopy(i) for i in ordered[offset : offset + limit]],
            total=len(ordered),
            offset=offset,
            limit=limit,
        )


class InMemoryUnitOfWork:
    """Simule la sémantique transactionnelle : rien n'est visible sans commit."""

    def __init__(self) -> None:
        self._committed = InMemoryInternRepository()
        self.interns = InMemoryInternRepository()
        self.committed = False

    def __enter__(self) -> Self:
        self.interns = copy.deepcopy(self._committed)
        self.committed = False
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.rollback()

    def commit(self) -> None:
        self._committed = copy.deepcopy(self.interns)
        self.committed = True

    def rollback(self) -> None:
        self.interns = copy.deepcopy(self._committed)
