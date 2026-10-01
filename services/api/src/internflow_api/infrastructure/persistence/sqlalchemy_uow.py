"""Adaptateur PostgreSQL des ports `InternRepository` et `UnitOfWork`."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from internflow_api.domain.exceptions import EmailAlreadyUsedError
from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.ports.repositories import Page
from internflow_api.domain.value_objects import Email
from internflow_api.infrastructure.persistence.mappers import intern_to_record, record_to_intern
from internflow_api.infrastructure.persistence.orm import (
    INTERN_EMAIL_UNIQUE_CONSTRAINT,
    InternRecord,
)


def build_engine(database_url: str, *, pool_size: int = 5) -> Engine:
    return create_engine(database_url, pool_size=pool_size, pool_pre_ping=True)


class SqlAlchemyInternRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, intern: Intern) -> None:
        self._session.add(intern_to_record(intern))
        try:
            # flush immédiat : la contrainte d'unicité de la base est la vraie garantie
            # (deux requêtes simultanées peuvent passer la vérification applicative).
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            if INTERN_EMAIL_UNIQUE_CONSTRAINT in str(exc.orig):
                raise EmailAlreadyUsedError(intern.email.value) from exc
            raise

    def get(self, intern_id: InternId) -> Intern | None:
        record = self._session.get(InternRecord, intern_id)
        return record_to_intern(record) if record else None

    def get_by_email(self, email: Email) -> Intern | None:
        record = self._session.scalar(select(InternRecord).where(InternRecord.email == email.value))
        return record_to_intern(record) if record else None

    def list(self, *, offset: int, limit: int) -> Page[Intern]:
        total = self._session.scalar(select(func.count()).select_from(InternRecord)) or 0
        records = self._session.scalars(
            select(InternRecord)
            .order_by(InternRecord.created_at.desc(), InternRecord.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return Page(
            items=[record_to_intern(r) for r in records],
            total=total,
            offset=offset,
            limit=limit,
        )


class SqlAlchemyUnitOfWork:
    interns: SqlAlchemyInternRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.interns = SqlAlchemyInternRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Tout ce qui n'a pas été explicitement validé est annulé.
        self.rollback()
        if self._session is not None:
            self._session.close()
            self._session = None

    def commit(self) -> None:
        if self._session is not None:
            self._session.commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
