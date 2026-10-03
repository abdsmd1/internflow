"""Adaptateurs en mémoire : pour les tests rapides et le prototypage.

Ils implémentent exactement les mêmes ports que les adaptateurs PostgreSQL.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from types import TracebackType
from typing import Self

from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import DateRange, Internship, InternshipId
from internflow_api.domain.ports.repositories import InternshipFilter, Page
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.user import User, UserId
from internflow_api.domain.value_objects import Email


def _paginate[T](items: Iterable[T], *, offset: int, limit: int) -> Page[T]:
    ordered = list(items)
    return Page(
        items=[copy.deepcopy(i) for i in ordered[offset : offset + limit]],
        total=len(ordered),
        offset=offset,
        limit=limit,
    )


def _newest_first[T: (Intern, Supervisor, Internship)](items: Iterable[T]) -> list[T]:
    return sorted(items, key=lambda i: (-i.created_at.timestamp(), str(i.id)))


def _find[T](items: Iterable[T], predicate: Callable[[T], bool]) -> T | None:
    found = next((i for i in items if predicate(i)), None)
    return copy.deepcopy(found) if found else None


@dataclass
class _Store:
    """État complet de la « base » en mémoire."""

    interns: dict[InternId, Intern] = field(default_factory=dict)
    supervisors: dict[SupervisorId, Supervisor] = field(default_factory=dict)
    internships: dict[InternshipId, Internship] = field(default_factory=dict)
    users: dict[UserId, User] = field(default_factory=dict)


class InMemoryInternRepository:
    def __init__(self, items: dict[InternId, Intern]) -> None:
        self._items = items

    def add(self, intern: Intern) -> None:
        self._items[intern.id] = copy.deepcopy(intern)

    def get(self, intern_id: InternId) -> Intern | None:
        return _find(self._items.values(), lambda i: i.id == intern_id)

    def get_by_email(self, email: Email) -> Intern | None:
        return _find(self._items.values(), lambda i: i.email == email)

    def list(self, *, offset: int, limit: int) -> Page[Intern]:
        return _paginate(_newest_first(self._items.values()), offset=offset, limit=limit)


class InMemorySupervisorRepository:
    def __init__(self, items: dict[SupervisorId, Supervisor]) -> None:
        self._items = items

    def add(self, supervisor: Supervisor) -> None:
        self._items[supervisor.id] = copy.deepcopy(supervisor)

    def get(self, supervisor_id: SupervisorId, *, for_update: bool = False) -> Supervisor | None:
        # Pas de concurrence en mémoire : le verrou n'a pas d'effet.
        return _find(self._items.values(), lambda s: s.id == supervisor_id)

    def get_by_email(self, email: Email) -> Supervisor | None:
        return _find(self._items.values(), lambda s: s.email == email)

    def list(self, *, offset: int, limit: int) -> Page[Supervisor]:
        return _paginate(_newest_first(self._items.values()), offset=offset, limit=limit)


class InMemoryInternshipRepository:
    def __init__(self, items: dict[InternshipId, Internship]) -> None:
        self._items = items

    def add(self, internship: Internship) -> None:
        self._items[internship.id] = copy.deepcopy(internship)

    def get(self, internship_id: InternshipId) -> Internship | None:
        return _find(self._items.values(), lambda i: i.id == internship_id)

    def save(self, internship: Internship) -> None:
        self._items[internship.id] = copy.deepcopy(internship)

    def list(self, criteria: InternshipFilter, *, offset: int, limit: int) -> Page[Internship]:
        matching = (
            i
            for i in self._items.values()
            if (criteria.intern_id is None or i.intern_id == criteria.intern_id)
            and (criteria.supervisor_id is None or i.supervisor_id == criteria.supervisor_id)
            and (criteria.status is None or i.status is criteria.status)
        )
        return _paginate(_newest_first(matching), offset=offset, limit=limit)

    def has_active_overlap(self, intern_id: InternId, period: DateRange) -> bool:
        return any(
            i.intern_id == intern_id and i.is_active and i.period.overlaps(period)
            for i in self._items.values()
        )

    def count_active_overlapping_for_supervisor(
        self, supervisor_id: SupervisorId, period: DateRange
    ) -> int:
        return sum(
            1
            for i in self._items.values()
            if i.supervisor_id == supervisor_id and i.is_active and i.period.overlaps(period)
        )


class InMemoryUserRepository:
    def __init__(self, items: dict[UserId, User]) -> None:
        self._items = items

    def add(self, user: User) -> None:
        self._items[user.id] = copy.deepcopy(user)

    def get_by_email(self, email: Email) -> User | None:
        return _find(self._items.values(), lambda u: u.email == email)

    def exists_for_profile(
        self, *, intern_id: InternId | None = None, supervisor_id: SupervisorId | None = None
    ) -> bool:
        return any(
            (intern_id is not None and u.intern_id == intern_id)
            or (supervisor_id is not None and u.supervisor_id == supervisor_id)
            for u in self._items.values()
        )


class InMemoryUnitOfWork:
    """Simule une transaction : rien n'est visible des autres sans `commit()`."""

    def __init__(self) -> None:
        self._committed_store = _Store()
        self.committed = False
        self._bind(copy.deepcopy(self._committed_store))

    def _bind(self, store: _Store) -> None:
        self._working_store = store
        self._interns = InMemoryInternRepository(store.interns)
        self._supervisors = InMemorySupervisorRepository(store.supervisors)
        self._internships = InMemoryInternshipRepository(store.internships)
        self._users = InMemoryUserRepository(store.users)

    @property
    def interns(self) -> InMemoryInternRepository:
        return self._interns

    @property
    def supervisors(self) -> InMemorySupervisorRepository:
        return self._supervisors

    @property
    def internships(self) -> InMemoryInternshipRepository:
        return self._internships

    @property
    def users(self) -> InMemoryUserRepository:
        return self._users

    def __enter__(self) -> Self:
        self.committed = False
        self._bind(copy.deepcopy(self._committed_store))
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.rollback()

    def commit(self) -> None:
        self._committed_store = copy.deepcopy(self._working_store)
        self.committed = True

    def rollback(self) -> None:
        self._bind(copy.deepcopy(self._committed_store))
