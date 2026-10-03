"""Fixtures partagées par toute la suite de tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from tests.factories import HR_EMAIL, FakeClock, fast_hasher
from tests.helpers import authenticated, build_client


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture(scope="session")
def hasher() -> Argon2PasswordHasher:
    return fast_hasher()


@pytest.fixture
def anonymous_client(
    uow: InMemoryUnitOfWork, clock: FakeClock, hasher: Argon2PasswordHasher
) -> Iterator[TestClient]:
    with build_client(uow, clock, hasher) as test_client:
        yield test_client


@pytest.fixture
def client(anonymous_client: TestClient) -> TestClient:
    """Client connecté en tant que RH (tous les droits)."""
    return authenticated(anonymous_client, HR_EMAIL)
