from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from internflow_api.domain.ports.repositories import (
    InternRepository,
    InternshipRepository,
    SupervisorRepository,
)


class UnitOfWork(Protocol):
    """Frontière transactionnelle d'un cas d'usage (pattern Unit of Work).

    Usage :
        with uow:
            uow.interns.add(intern)
            uow.commit()

    Si `commit()` n'est pas appelé, la sortie du bloc annule tout (rollback).
    Tous les repositories d'une même unité de travail partagent la même transaction.
    """

    # Propriétés en lecture seule : chaque adaptateur peut exposer son propre
    # type de repository (covariance), tant qu'il respecte le port.
    @property
    def interns(self) -> InternRepository: ...

    @property
    def supervisors(self) -> SupervisorRepository: ...

    @property
    def internships(self) -> InternshipRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
