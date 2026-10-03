from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from internflow_api.infrastructure.persistence.in_memory import InMemoryUnitOfWork
from internflow_api.infrastructure.security.argon2_hasher import Argon2PasswordHasher
from tests.factories import (
    HR_EMAIL,
    FakeClock,
    intern_payload,
    internship_payload,
    supervisor_payload,
)
from tests.helpers import authenticated, build_client

SUPERVISORS = "/api/v1/supervisors"
INTERNSHIPS = "/api/v1/internships"


def create_intern(client: TestClient, email: str = "sara@example.com") -> str:
    response = client.post("/api/v1/interns", json=intern_payload(email=email))
    assert response.status_code == 201
    return str(response.json()["id"])


def create_supervisor(client: TestClient, **overrides: object) -> str:
    response = client.post(SUPERVISORS, json=supervisor_payload(**overrides))
    assert response.status_code == 201
    return str(response.json()["id"])


class TestSupervisorsEndpoints:
    def test_create_read_and_list(self, client: TestClient) -> None:
        created = client.post(SUPERVISORS, json=supervisor_payload(max_interns=3))

        assert created.status_code == 201
        body = created.json()
        assert body["max_interns"] == 3
        assert client.get(created.headers["Location"]).json() == body
        assert client.get(SUPERVISORS).json()["total"] == 1

    def test_default_capacity(self, client: TestClient) -> None:
        assert client.post(SUPERVISORS, json=supervisor_payload()).json()["max_interns"] == 5

    def test_duplicate_email(self, client: TestClient) -> None:
        client.post(SUPERVISORS, json=supervisor_payload())
        response = client.post(SUPERVISORS, json=supervisor_payload())
        assert response.status_code == 409
        assert response.json()["type"].endswith("/email-already-used")

    @pytest.mark.parametrize("capacity", [0, 11])
    def test_capacity_bounds_are_validated(self, client: TestClient, capacity: int) -> None:
        response = client.post(SUPERVISORS, json=supervisor_payload(max_interns=capacity))
        assert response.status_code == 422

    def test_unknown_supervisor(self, client: TestClient) -> None:
        response = client.get(f"{SUPERVISORS}/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["type"].endswith("/supervisor-not-found")


class TestPlanInternshipEndpoint:
    def test_plans_an_internship(self, client: TestClient) -> None:
        payload = internship_payload(create_intern(client), create_supervisor(client))

        response = client.post(INTERNSHIPS, json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "planned"
        assert body["duration_days"] == 124
        assert response.headers["Location"] == f"{INTERNSHIPS}/{body['id']}"

    def test_end_before_start_is_rejected(self, client: TestClient) -> None:
        payload = internship_payload(
            create_intern(client), create_supervisor(client), end_date="2026-10-01"
        )
        response = client.post(INTERNSHIPS, json=payload)
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-value")

    def test_unknown_intern_returns_404(self, client: TestClient) -> None:
        response = client.post(
            INTERNSHIPS, json=internship_payload(str(uuid4()), create_supervisor(client))
        )
        assert response.status_code == 404
        assert response.json()["type"].endswith("/intern-not-found")

    def test_overlap_returns_409(self, client: TestClient) -> None:
        intern = create_intern(client)
        client.post(INTERNSHIPS, json=internship_payload(intern, create_supervisor(client)))
        other = create_supervisor(client, email="nadia@example.com")

        response = client.post(
            INTERNSHIPS,
            json=internship_payload(intern, other, start_date="2026-12-01", end_date="2027-03-01"),
        )

        assert response.status_code == 409
        assert response.json()["type"].endswith("/internship-overlap")

    def test_supervisor_capacity_returns_409(self, client: TestClient) -> None:
        supervisor = create_supervisor(client, max_interns=1)
        client.post(INTERNSHIPS, json=internship_payload(create_intern(client), supervisor))

        response = client.post(
            INTERNSHIPS,
            json=internship_payload(create_intern(client, "amine@example.com"), supervisor),
        )

        assert response.status_code == 409
        assert response.json()["type"].endswith("/supervisor-capacity-exceeded")


class TestListInternshipsEndpoint:
    def test_filters(self, client: TestClient) -> None:
        sara, amine = create_intern(client), create_intern(client, "amine@example.com")
        karim = create_supervisor(client)
        client.post(INTERNSHIPS, json=internship_payload(sara, karim))
        client.post(INTERNSHIPS, json=internship_payload(amine, karim))

        assert client.get(INTERNSHIPS, params={"supervisor_id": karim}).json()["total"] == 2
        assert client.get(INTERNSHIPS, params={"intern_id": sara}).json()["total"] == 1
        assert client.get(INTERNSHIPS, params={"status": "ongoing"}).json()["total"] == 0

    def test_unknown_status_filter_is_rejected(self, client: TestClient) -> None:
        assert client.get(INTERNSHIPS, params={"status": "archived"}).status_code == 422


class TestInternshipLifecycleEndpoints:
    @pytest.fixture
    def client_on_start_date(self, hasher: Argon2PasswordHasher) -> Iterator[TestClient]:
        """Application (connectée en RH) dont l'horloge est au premier jour du stage."""
        clock = FakeClock(datetime(2026, 10, 5, 8, 0, tzinfo=UTC))
        with build_client(InMemoryUnitOfWork(), clock, hasher) as client:
            yield authenticated(client, HR_EMAIL)

    def test_full_lifecycle(self, client_on_start_date: TestClient) -> None:
        client = client_on_start_date
        internship = client.post(
            INTERNSHIPS, json=internship_payload(create_intern(client), create_supervisor(client))
        ).json()
        url = f"{INTERNSHIPS}/{internship['id']}"

        assert client.post(f"{url}/start").json()["status"] == "ongoing"
        assert client.post(f"{url}/complete").json()["status"] == "completed"
        assert client.get(url).json()["status"] == "completed"

        refused = client.post(f"{url}/cancel")
        assert refused.status_code == 409
        assert refused.json()["type"].endswith("/invalid-status-transition")

    def test_cannot_start_before_start_date(self, client: TestClient) -> None:
        internship = client.post(
            INTERNSHIPS, json=internship_payload(create_intern(client), create_supervisor(client))
        ).json()

        response = client.post(f"{INTERNSHIPS}/{internship['id']}/start")

        assert response.status_code == 409
        assert response.json()["type"].endswith("/internship-not-startable-yet")

    def test_cancel_planned_internship(self, client: TestClient) -> None:
        internship = client.post(
            INTERNSHIPS, json=internship_payload(create_intern(client), create_supervisor(client))
        ).json()
        response = client.post(f"{INTERNSHIPS}/{internship['id']}/cancel")
        assert response.json()["status"] == "cancelled"

    def test_unknown_internship(self, client: TestClient) -> None:
        assert client.get(f"{INTERNSHIPS}/{uuid4()}").status_code == 404
        response = client.post(f"{INTERNSHIPS}/{uuid4()}/start")
        assert response.status_code == 404
        assert response.json()["type"].endswith("/internship-not-found")
