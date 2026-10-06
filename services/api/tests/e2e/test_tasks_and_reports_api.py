"""Tâches et rapports hebdomadaires, de bout en bout (HTTP), avec les vrais rôles."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
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


@pytest.fixture
def stage(client: TestClient) -> Stage:
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


class TestTaskFlow:
    def test_supervisor_assigns_and_intern_completes(self, stage: Stage) -> None:
        karim = stage.as_karim()
        created = karim.post(
            stage.tasks_url, json={"title": "Modéliser le schéma", "due_date": "2026-10-15"}
        )
        assert created.status_code == 201
        task = created.json()
        assert (task["status"], task["is_overdue"]) == ("todo", False)

        sara = stage.as_sara()
        assert sara.post(f"{API}/tasks/{task['id']}/start").json()["status"] == "in_progress"
        done = sara.post(f"{API}/tasks/{task['id']}/complete").json()
        assert done["status"] == "done"
        assert done["completed_at"] is not None

        [listed] = sara.get(stage.tasks_url).json()
        assert listed["status"] == "done"

    def test_intern_cannot_assign_tasks(self, stage: Stage) -> None:
        response = stage.as_sara().post(
            stage.tasks_url, json={"title": "Auto-assignée", "due_date": "2026-10-15"}
        )
        assert response.status_code == 403

    def test_due_date_outside_internship(self, stage: Stage) -> None:
        response = stage.as_karim().post(
            stage.tasks_url, json={"title": "Trop tard", "due_date": "2027-06-01"}
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/invalid-value")

    def test_completing_twice_is_a_conflict(self, stage: Stage) -> None:
        task_id = (
            stage.as_karim()
            .post(stage.tasks_url, json={"title": "Une fois", "due_date": "2026-10-15"})
            .json()["id"]
        )
        sara = stage.as_sara()
        sara.post(f"{API}/tasks/{task_id}/complete")
        response = sara.post(f"{API}/tasks/{task_id}/complete")
        assert response.status_code == 409
        assert response.json()["type"].endswith("/invalid-status-transition")


class TestReportFlow:
    def test_intern_submits_and_supervisor_reviews(self, stage: Stage) -> None:
        submitted = stage.as_sara().post(
            stage.reports_url,
            json={
                "week": "2026-W40",
                "accomplishments": "Prise en main du projet et de la base.",
                "difficulties": "Accès VPN",
            },
        )
        assert submitted.status_code == 201
        report = submitted.json()
        assert (report["week_start"], report["week_end"]) == ("2026-09-28", "2026-10-04")

        reviewed = stage.as_karim().post(
            f"{API}/reports/{report['id']}/review", json={"feedback": "Bon début."}
        )
        assert reviewed.json()["status"] == "reviewed"

        [listed] = stage.as_sara().get(stage.reports_url).json()
        assert listed["feedback"] == "Bon début."

    def test_one_report_per_week(self, stage: Stage) -> None:
        sara = stage.as_sara()
        body = {"week": "2026-W40", "accomplishments": "Semaine 40"}
        sara.post(stage.reports_url, json=body)
        response = sara.post(stage.reports_url, json=body)
        assert response.status_code == 409
        assert response.json()["type"].endswith("/report-already-submitted")

    @pytest.mark.parametrize(
        ("week", "expected_type"),
        [
            ("2026-40", "validation-error"),
            ("2025-W53", "invalid-value"),
            ("2026-W45", "invalid-value"),
        ],
    )
    def test_invalid_weeks(self, stage: Stage, week: str, expected_type: str) -> None:
        # format invalide / semaine inexistante / semaine future
        response = stage.as_sara().post(
            stage.reports_url, json={"week": week, "accomplishments": "…"}
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith(f"/{expected_type}")

    def test_supervisor_cannot_write_the_report(self, stage: Stage) -> None:
        response = stage.as_karim().post(
            stage.reports_url, json={"week": "2026-W40", "accomplishments": "À sa place"}
        )
        assert response.status_code == 403

    def test_intern_cannot_review_own_report(self, stage: Stage) -> None:
        sara = stage.as_sara()
        report_id = sara.post(
            stage.reports_url, json={"week": "2026-W40", "accomplishments": "Semaine 40"}
        ).json()["id"]
        response = sara.post(f"{API}/reports/{report_id}/review", json={"feedback": "Parfait"})
        assert response.status_code == 403


def test_openapi_documents_authentication_errors(client: TestClient) -> None:
    responses = client.get("/openapi.json").json()["paths"]["/api/v1/interns"]["get"]["responses"]
    assert {"401", "403"} <= responses.keys()
