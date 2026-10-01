"""Fixtures partagées par toute la suite de tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from internflow_api.config import Environment, Settings
from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.main import create_app
from tests.factories import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


@pytest.fixture
def client(uow: InMemoryUnitOfWork, clock: FakeClock) -> Iterator[TestClient]:
    settings = Settings(environment=Environment.TEST, log_level="WARNING")
    app = create_app(settings, uow_factory=lambda: uow, clock=clock)
    with TestClient(app) as test_client:
        yield test_client
