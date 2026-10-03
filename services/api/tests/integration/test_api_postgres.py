"""L'application complète, câblée sur PostgreSQL comme en production."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from internflow_api.application.users import RegisterUser, RegisterUserCommand
from internflow_api.domain.user import Role
from internflow_api.infrastructure.clock import SystemClock
from internflow_api.infrastructure.persistence.sqlalchemy_uow import SqlAlchemyUnitOfWork
from internflow_api.main import create_app
from tests.factories import HR_EMAIL, TEST_PASSWORD, fast_hasher, intern_payload, make_settings
from tests.helpers import authenticated

pytestmark = pytest.mark.integration


@pytest.fixture
def client(engine: Engine, database_url: str) -> Iterator[TestClient]:
    # `engine` garantit que les migrations sont appliquées avant le démarrage.
    hasher = fast_hasher()
    uow = SqlAlchemyUnitOfWork(sessionmaker(bind=engine, expire_on_commit=False))
    RegisterUser(uow, SystemClock(), hasher).execute(
        RegisterUserCommand(HR_EMAIL, TEST_PASSWORD, Role.HR)
    )
    settings = make_settings(database_url=PostgresDsn(database_url))
    with TestClient(create_app(settings, password_hasher=hasher)) as test_client:
        yield authenticated(test_client, HR_EMAIL)


def test_register_then_read_through_postgres(client: TestClient) -> None:
    created = client.post("/api/v1/interns", json=intern_payload())
    assert created.status_code == 201

    fetched = client.get(created.headers["Location"])
    assert fetched.json() == created.json()

    duplicate = client.post("/api/v1/interns", json=intern_payload())
    assert duplicate.status_code == 409


def test_account_is_persisted_and_password_hashed(client: TestClient, engine: Engine) -> None:
    assert client.get("/api/v1/auth/me").json()["role"] == "hr"
    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT password_hash FROM users WHERE email = :e"), {"e": HR_EMAIL}
        ).scalar_one()
    assert stored.startswith("$argon2id$")
    assert TEST_PASSWORD not in stored


def test_database_enforces_role_profile_consistency(engine: Engine) -> None:
    """Contrainte CHECK : même en contournant le domaine, un stagiaire sans profil est refusé."""
    with engine.begin() as connection, pytest.raises(IntegrityError, match="profile_matches_role"):
        connection.execute(
            text(
                "INSERT INTO users (id, email, password_hash, role, is_active, created_at) "
                "VALUES (gen_random_uuid(), 'x@example.com', 'h', 'intern', true, now())"
            )
        )


def test_readiness_checks_the_database(client: TestClient) -> None:
    assert client.get("/health/ready").json() == {"status": "ok"}
