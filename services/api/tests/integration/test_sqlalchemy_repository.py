"""Tests d'intégration de l'adaptateur PostgreSQL.

Ils démarrent un vrai PostgreSQL dans Docker (Testcontainers) et appliquent
les migrations Alembic : on teste ce qui tournera réellement en production.
Ils sont ignorés automatiquement si Docker n'est pas disponible.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from internflow_api.application.interns import (
    GetIntern,
    ListInterns,
    RegisterIntern,
    RegisterInternCommand,
)
from internflow_api.domain.exceptions import EmailAlreadyUsedError
from internflow_api.domain.intern import Intern, InternId
from internflow_api.domain.value_objects import Email, PersonName, StudyLevel
from internflow_api.infrastructure.persistence.sqlalchemy_uow import SqlAlchemyUnitOfWork
from tests.factories import FIXED_NOW, HR, FakeClock

pytestmark = pytest.mark.integration


@pytest.fixture
def uow(engine: Engine) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))


def _command(email: str) -> RegisterInternCommand:
    return RegisterInternCommand("Sara", "El Amrani", email, "ENSA Oujda", StudyLevel.INGENIEUR)


def test_round_trip(uow: SqlAlchemyUnitOfWork) -> None:
    created = RegisterIntern(uow, FakeClock()).execute(HR, _command("sara@example.com"))

    loaded = GetIntern(uow).execute(HR, created.id)

    assert loaded == created
    assert loaded.email == Email("sara@example.com")
    assert loaded.created_at == FIXED_NOW


def test_database_constraint_guarantees_unique_email(uow: SqlAlchemyUnitOfWork) -> None:
    """Simule une course : on contourne la vérification applicative."""
    first = Intern(
        name=PersonName("A", "B"),
        email=Email("dup@example.com"),
        school="ENSA",
        study_level=StudyLevel.LICENCE,
        created_at=FIXED_NOW,
    )
    second = Intern(
        name=PersonName("C", "D"),
        email=Email("dup@example.com"),
        school="ENSA",
        study_level=StudyLevel.LICENCE,
        created_at=FIXED_NOW,
        id=InternId(uuid4()),
    )
    with uow:
        uow.interns.add(first)
        uow.commit()
    with uow, pytest.raises(EmailAlreadyUsedError):
        uow.interns.add(second)


def test_uncommitted_changes_are_rolled_back(uow: SqlAlchemyUnitOfWork) -> None:
    with uow:
        uow.interns.add(
            Intern(
                name=PersonName("A", "B"),
                email=Email("rollback@example.com"),
                school="ENSA",
                study_level=StudyLevel.LICENCE,
                created_at=FIXED_NOW,
            )
        )
        # pas de commit

    assert ListInterns(uow).execute(HR).total == 0
