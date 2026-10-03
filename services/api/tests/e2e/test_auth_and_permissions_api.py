"""Authentification et matrice des droits, testées de bout en bout (HTTP)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.factories import (
    FIXED_NOW,
    HR_EMAIL,
    TEST_PASSWORD,
    FakeClock,
    intern_payload,
    internship_payload,
    supervisor_payload,
)
from tests.helpers import authenticated, login

API = "/api/v1"


# ------------------------------------------------------------- authentification
class TestLogin:
    def test_login_returns_an_oauth2_bearer_token(self, anonymous_client: TestClient) -> None:
        response = anonymous_client.post(
            f"{API}/auth/token", data={"username": HR_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 1800

    def test_wrong_password(self, anonymous_client: TestClient) -> None:
        response = anonymous_client.post(
            f"{API}/auth/token", data={"username": HR_EMAIL, "password": "mauvais-mot-de-passe"}
        )
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["type"].endswith("/invalid-credentials")

    def test_me(self, client: TestClient) -> None:
        body = client.get(f"{API}/auth/me").json()
        assert body["role"] == "hr"
        assert body["intern_id"] is None


class TestProtectedRoutes:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/interns"),
            ("POST", "/interns"),
            ("GET", "/supervisors"),
            ("GET", "/internships"),
            ("POST", "/users"),
            ("GET", "/auth/me"),
        ],
    )
    def test_requests_without_token_are_rejected(
        self, anonymous_client: TestClient, method: str, path: str
    ) -> None:
        response = anonymous_client.request(method, f"{API}{path}", json={})
        assert response.status_code == 401
        assert response.json()["type"].endswith("/invalid-token")
        assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_forged_token_is_rejected(self, anonymous_client: TestClient) -> None:
        anonymous_client.headers["Authorization"] = "Bearer faux.jeton.signe"
        assert anonymous_client.get(f"{API}/interns").status_code == 401

    def test_expired_token_is_rejected(self, client: TestClient, clock: FakeClock) -> None:
        clock._current = FIXED_NOW + timedelta(hours=1)  # le jeton (30 min) a expiré
        assert client.get(f"{API}/auth/me").status_code == 401

    def test_health_probes_stay_public(self, anonymous_client: TestClient) -> None:
        assert anonymous_client.get("/health/live").status_code == 200
        assert anonymous_client.get("/health/ready").status_code == 200


# --------------------------------------------------------------- matrice des droits
@dataclass
class Organisation:
    """Deux binômes encadrant / stagiaire, et les comptes associés."""

    client: TestClient
    sara_id: str
    amine_id: str
    karim_id: str
    sara_internship: str
    amine_internship: str

    def as_hr(self) -> TestClient:
        return authenticated(self.client, HR_EMAIL)

    def as_karim(self) -> TestClient:
        return authenticated(self.client, "karim@example.com")

    def as_sara(self) -> TestClient:
        return authenticated(self.client, "sara@example.com")


@pytest.fixture
def org(client: TestClient) -> Organisation:
    def create(path: str, payload: dict[str, object]) -> str:
        response = client.post(f"{API}{path}", json=payload)
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    sara = create("/interns", intern_payload(email="sara@example.com"))
    amine = create("/interns", intern_payload(email="amine@example.com"))
    karim = create("/supervisors", supervisor_payload(email="karim@example.com"))
    nadia = create("/supervisors", supervisor_payload(email="nadia@example.com"))
    sara_internship = create("/internships", internship_payload(sara, karim))
    amine_internship = create("/internships", internship_payload(amine, nadia))
    for email, role, link in [
        ("karim@example.com", "supervisor", {"supervisor_id": karim}),
        ("sara@example.com", "intern", {"intern_id": sara}),
    ]:
        create("/users", {"email": email, "password": TEST_PASSWORD, "role": role, **link})
    return Organisation(client, sara, amine, karim, sara_internship, amine_internship)


class TestUserAccounts:
    def test_created_account_can_log_in_and_never_exposes_password(self, org: Organisation) -> None:
        client = org.as_hr()
        response = client.post(
            f"{API}/users",
            json={"email": "rh2@example.com", "password": TEST_PASSWORD, "role": "hr"},
        )
        assert response.status_code == 201
        assert "password" not in response.text
        assert login(client, "rh2@example.com")

    def test_profile_can_only_have_one_account(self, org: Organisation) -> None:
        response = org.as_hr().post(
            f"{API}/users",
            json={
                "email": "sara.bis@example.com",
                "password": TEST_PASSWORD,
                "role": "intern",
                "intern_id": org.sara_id,
            },
        )
        assert response.status_code == 409
        assert response.json()["type"].endswith("/account-already-linked")

    def test_weak_password_is_rejected(self, org: Organisation) -> None:
        response = org.as_hr().post(
            f"{API}/users", json={"email": "x@example.com", "password": "court", "role": "hr"}
        )
        assert response.status_code == 422

    def test_non_hr_cannot_create_accounts(self, org: Organisation) -> None:
        response = org.as_karim().post(
            f"{API}/users",
            json={"email": "pirate@example.com", "password": TEST_PASSWORD, "role": "hr"},
        )
        assert response.status_code == 403
        assert response.json()["type"].endswith("/permission-denied")


class TestSupervisorPermissions:
    def test_sees_only_own_internships(self, org: Organisation) -> None:
        client = org.as_karim()
        listing = client.get(f"{API}/internships").json()
        assert [i["id"] for i in listing["items"]] == [org.sara_internship]
        # Même en demandant explicitement ceux d'un autre encadrant.
        other = client.get(f"{API}/internships", params={"intern_id": org.amine_id}).json()
        assert other["total"] == 0

    def test_other_internship_looks_nonexistent(self, org: Organisation) -> None:
        response = org.as_karim().get(f"{API}/internships/{org.amine_internship}")
        assert response.status_code == 404

    def test_can_read_interns_but_not_create_them(self, org: Organisation) -> None:
        client = org.as_karim()
        assert client.get(f"{API}/interns").json()["total"] == 2
        response = client.post(f"{API}/interns", json=intern_payload(email="new@example.com"))
        assert response.status_code == 403

    def test_can_progress_but_not_cancel_own_internship(
        self, org: Organisation, clock: FakeClock
    ) -> None:
        clock._current = FIXED_NOW.replace(day=5)  # premier jour du stage
        client = org.as_karim()
        assert client.post(f"{API}/internships/{org.sara_internship}/start").status_code == 200
        response = client.post(f"{API}/internships/{org.sara_internship}/cancel")
        assert response.status_code == 403

    def test_cannot_plan_internships(self, org: Organisation) -> None:
        response = org.as_karim().post(
            f"{API}/internships", json=internship_payload(org.amine_id, org.karim_id)
        )
        assert response.status_code == 403


class TestInternPermissions:
    def test_sees_only_own_internship(self, org: Organisation) -> None:
        client = org.as_sara()
        listing = client.get(f"{API}/internships").json()
        assert [i["id"] for i in listing["items"]] == [org.sara_internship]
        assert client.get(f"{API}/internships/{org.amine_internship}").status_code == 404

    def test_sees_own_profile_only(self, org: Organisation) -> None:
        client = org.as_sara()
        assert client.get(f"{API}/interns/{org.sara_id}").status_code == 200
        assert client.get(f"{API}/interns/{org.amine_id}").status_code == 404
        assert client.get(f"{API}/interns").status_code == 403

    def test_cannot_change_internship_status(self, org: Organisation) -> None:
        client = org.as_sara()
        for action in ("start", "complete", "cancel"):
            response = client.post(f"{API}/internships/{org.sara_internship}/{action}")
            assert response.status_code == 403, action

    def test_can_consult_supervisors(self, org: Organisation) -> None:
        client = org.as_sara()
        assert client.get(f"{API}/supervisors/{org.karim_id}").status_code == 200

    def test_unknown_resources_still_404(self, org: Organisation) -> None:
        assert org.as_sara().get(f"{API}/internships/{uuid4()}").status_code == 404
