"""Un stage en cours avec ses trois rôles (RH, encadrant Karim, stagiaire Sara)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from tests.factories import (
    HR_EMAIL,
    TEST_PASSWORD,
    intern_payload,
    internship_payload,
    supervisor_payload,
)
from tests.helpers import authenticated

API = "/api/v1"


@dataclass
class Stage:
    client: TestClient
    internship_id: str

    def as_hr(self) -> TestClient:
        return authenticated(self.client, HR_EMAIL)

    def as_karim(self) -> TestClient:
        return authenticated(self.client, "karim@example.com")

    def as_sara(self) -> TestClient:
        return authenticated(self.client, "sara@example.com")

    @property
    def tasks_url(self) -> str:
        return f"{API}/internships/{self.internship_id}/tasks"

    @property
    def reports_url(self) -> str:
        return f"{API}/internships/{self.internship_id}/reports"


def make_stage(client: TestClient) -> Stage:
    """Stage EN COURS de Sara, encadrée par Karim (horloge de test : 1er octobre 2026)."""

    def create(path: str, payload: dict[str, object]) -> str:
        response = client.post(f"{API}{path}", json=payload)
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    sara = create("/interns", intern_payload(email="sara@example.com"))
    karim = create("/supervisors", supervisor_payload(email="karim@example.com"))
    internship = create(
        "/internships",
        internship_payload(sara, karim, start_date="2026-10-01", end_date="2027-02-28"),
    )
    create(
        "/users",
        {
            "email": "karim@example.com",
            "password": TEST_PASSWORD,
            "role": "supervisor",
            "supervisor_id": karim,
        },
    )
    create(
        "/users",
        {
            "email": "sara@example.com",
            "password": TEST_PASSWORD,
            "role": "intern",
            "intern_id": sara,
        },
    )
    assert client.post(f"{API}/internships/{internship}/start").status_code == 200
    return Stage(client, internship)
