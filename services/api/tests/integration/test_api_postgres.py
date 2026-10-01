"""L'application complète, câblée sur PostgreSQL comme en production."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import PostgresDsn

from internflow_api.config import Environment, Settings
from internflow_api.main import create_app
from tests.factories import intern_payload

pytestmark = pytest.mark.integration


@pytest.fixture
def client(engine: object, database_url: str) -> Iterator[TestClient]:
    # `engine` garantit que les migrations sont appliquées avant le démarrage.
    settings = Settings(
        environment=Environment.TEST,
        log_level="WARNING",
        database_url=PostgresDsn(database_url),
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_register_then_read_through_postgres(client: TestClient) -> None:
    created = client.post("/api/v1/interns", json=intern_payload())
    assert created.status_code == 201

    fetched = client.get(created.headers["Location"])
    assert fetched.json() == created.json()

    duplicate = client.post("/api/v1/interns", json=intern_payload())
    assert duplicate.status_code == 409


def test_readiness_checks_the_database(client: TestClient) -> None:
    assert client.get("/health/ready").json() == {"status": "ok"}
