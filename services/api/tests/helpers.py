"""Helpers d'authentification pour les tests HTTP."""

from __future__ import annotations

from fastapi.testclient import TestClient

from internflow_api.application.users import RegisterUser, RegisterUserCommand
from internflow_api.domain.user import Role
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from internflow_api.main import create_app
from tests.factories import HR_EMAIL, TEST_PASSWORD, FakeClock, make_settings


def login(client: TestClient, email: str, password: str = TEST_PASSWORD) -> str:
    response = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def build_client(
    uow: InMemoryUnitOfWork, clock: FakeClock, hasher: Argon2PasswordHasher
) -> TestClient:
    """Application en mémoire avec un compte RH déjà créé (comme via la CLI)."""
    RegisterUser(uow, clock, hasher).execute(
        RegisterUserCommand(email=HR_EMAIL, password=TEST_PASSWORD, role=Role.HR)
    )
    app = create_app(make_settings(), uow_factory=lambda: uow, clock=clock, password_hasher=hasher)
    return TestClient(app)


def authenticated(client: TestClient, email: str, password: str = TEST_PASSWORD) -> TestClient:
    """Connecte le client avec ce compte (remplace l'éventuel jeton précédent)."""
    client.headers["Authorization"] = f"Bearer {login(client, email, password)}"
    return client
