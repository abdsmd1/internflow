"""Adaptateurs PostgreSQL des ports Repository et Unit of Work."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import Engine, Select, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from internflow_api.domain.exceptions import (
    EmailAlreadyUsedError,
    InternshipNotFoundError,
    InternshipOverlapError,
)
from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.internship import (
    ACTIVE_STATUSES,
    DateRange,
    Internship,
    InternshipId,
)
from internflow_api.domain.ports.repositories import InternshipFilter, Page
from internflow_api.domain.supervisor import Supervisor, SupervisorId
from internflow_api.domain.value_objects import Email
from internflow_api.infrastructure.persistence.mappers import (
    intern_to_record,
    internship_to_record,
    record_to_intern,
    record_to_internship,
    record_to_supervisor,
    supervisor_to_record,
    update_internship_record,
)
from internflow_api.infrastructure.persistence.orm import (
    INTERN_EMAIL_UNIQUE_CONSTRAINT,
    INTERNSHIP_OVERLAP_CONSTRAINT,
    SUPERVISOR_EMAIL_UNIQUE_CONSTRAINT,
    InternRecord,
    InternshipRecord,
    SupervisorRecord,
)

_ACTIVE_STATUS_VALUES = sorted(s.value for s in ACTIVE_STATUSES)


def build_engine(database_url: str, *, pool_size: int = 5) -> Engine:
    return create_engine(database_url, pool_size=pool_size, pool_pre_ping=True)


def _violated_constraint(exc: IntegrityError) -> str | None:
    """Nom de la contrainte violée, fourni par le pilote psycopg."""
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def _flush(session: Session, errors: dict[str, Exception]) -> None:
    """Envoie les écritures à la base et traduit les violations de contraintes connues.

    La base est la garantie ultime : deux requêtes simultanées peuvent passer
    les vérifications applicatives, mais jamais ses contraintes.
    """
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        constraint = _violated_constraint(exc)
        if constraint in errors:
            raise errors[constraint] from exc
        raise


def _page[R](
    session: Session, query: Select[tuple[R]], *, offset: int, limit: int
) -> tuple[list[R], int]:
    """Exécute une requête paginée et renvoie (enregistrements, total)."""
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    records = list(session.scalars(query.offset(offset).limit(limit)).all())
    return records, total


class SqlAlchemyInternRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, intern: Intern) -> None:
        self._session.add(intern_to_record(intern))
        _flush(
            self._session,
            {INTERN_EMAIL_UNIQUE_CONSTRAINT: EmailAlreadyUsedError(intern.email.value)},
        )

    def get(self, intern_id: InternId) -> Intern | None:
        record = self._session.get(InternRecord, intern_id)
        return record_to_intern(record) if record else None

    def get_by_email(self, email: Email) -> Intern | None:
        record = self._session.scalar(select(InternRecord).where(InternRecord.email == email.value))
        return record_to_intern(record) if record else None

    def list(self, *, offset: int, limit: int) -> Page[Intern]:
        query = select(InternRecord).order_by(InternRecord.created_at.desc(), InternRecord.id)
        records, total = _page(self._session, query, offset=offset, limit=limit)
        return Page([record_to_intern(r) for r in records], total, offset, limit)


class SqlAlchemySupervisorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, supervisor: Supervisor) -> None:
        self._session.add(supervisor_to_record(supervisor))
        _flush(
            self._session,
            {SUPERVISOR_EMAIL_UNIQUE_CONSTRAINT: EmailAlreadyUsedError(supervisor.email.value)},
        )

    def get(self, supervisor_id: SupervisorId, *, for_update: bool = False) -> Supervisor | None:
        # SELECT … FOR UPDATE : la ligne reste verrouillée jusqu'au commit / rollback.
        record = self._session.get(SupervisorRecord, supervisor_id, with_for_update=for_update)
        return record_to_supervisor(record) if record else None

    def get_by_email(self, email: Email) -> Supervisor | None:
        record = self._session.scalar(
            select(SupervisorRecord).where(SupervisorRecord.email == email.value)
        )
        return record_to_supervisor(record) if record else None

    def list(self, *, offset: int, limit: int) -> Page[Supervisor]:
        query = select(SupervisorRecord).order_by(
            SupervisorRecord.created_at.desc(), SupervisorRecord.id
        )
        records, total = _page(self._session, query, offset=offset, limit=limit)
        return Page([record_to_supervisor(r) for r in records], total, offset, limit)


class SqlAlchemyInternshipRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, internship: Internship) -> None:
        self._session.add(internship_to_record(internship))
        _flush(
            self._session,
            {INTERNSHIP_OVERLAP_CONSTRAINT: InternshipOverlapError(internship.intern_id)},
        )

    def get(self, internship_id: InternshipId) -> Internship | None:
        record = self._session.get(InternshipRecord, internship_id)
        return record_to_internship(record) if record else None

    def save(self, internship: Internship) -> None:
        record = self._session.get(InternshipRecord, internship.id)
        if record is None:
            raise InternshipNotFoundError(internship.id)
        update_internship_record(record, internship)
        _flush(
            self._session,
            {INTERNSHIP_OVERLAP_CONSTRAINT: InternshipOverlapError(internship.intern_id)},
        )

    def list(self, criteria: InternshipFilter, *, offset: int, limit: int) -> Page[Internship]:
        query = select(InternshipRecord)
        if criteria.intern_id is not None:
            query = query.where(InternshipRecord.intern_id == criteria.intern_id)
        if criteria.supervisor_id is not None:
            query = query.where(InternshipRecord.supervisor_id == criteria.supervisor_id)
        if criteria.status is not None:
            query = query.where(InternshipRecord.status == criteria.status.value)
        query = query.order_by(InternshipRecord.created_at.desc(), InternshipRecord.id)
        records, total = _page(self._session, query, offset=offset, limit=limit)
        return Page([record_to_internship(r) for r in records], total, offset, limit)

    def _active_overlapping(self, period: DateRange) -> Select[tuple[int]]:
        return (
            select(func.count())
            .select_from(InternshipRecord)
            .where(
                InternshipRecord.status.in_(_ACTIVE_STATUS_VALUES),
                InternshipRecord.start_date <= period.end,
                InternshipRecord.end_date >= period.start,
            )
        )

    def has_active_overlap(self, intern_id: InternId, period: DateRange) -> bool:
        query = self._active_overlapping(period).where(InternshipRecord.intern_id == intern_id)
        return (self._session.scalar(query) or 0) > 0

    def count_active_overlapping_for_supervisor(
        self, supervisor_id: SupervisorId, period: DateRange
    ) -> int:
        query = self._active_overlapping(period).where(
            InternshipRecord.supervisor_id == supervisor_id
        )
        return self._session.scalar(query) or 0


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def _require_session(self) -> Session:
        if self._session is None:
            raise RuntimeError("L'unité de travail doit être utilisée dans un bloc `with`.")
        return self._session

    @property
    def interns(self) -> SqlAlchemyInternRepository:
        return SqlAlchemyInternRepository(self._require_session())

    @property
    def supervisors(self) -> SqlAlchemySupervisorRepository:
        return SqlAlchemySupervisorRepository(self._require_session())

    @property
    def internships(self) -> SqlAlchemyInternshipRepository:
        return SqlAlchemyInternshipRepository(self._require_session())

    def __enter__(self) -> Self:
        self._session = self._session_factory()
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
        self._require_session().commit()

    def rollback(self) -> None:
        if self._session is not None:
            self._session.rollback()
