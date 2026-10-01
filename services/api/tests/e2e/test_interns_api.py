from uuid import uuid4

from fastapi.testclient import TestClient

from tests.factories import intern_payload

BASE = "/api/v1/interns"


class TestRegisterInternEndpoint:
    def test_creates_intern(self, client: TestClient) -> None:
        response = client.post(BASE, json=intern_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "sara.elamrani@example.com"
        assert response.headers["Location"] == f"{BASE}/{body['id']}"

    def test_duplicate_email_returns_problem_details(self, client: TestClient) -> None:
        client.post(BASE, json=intern_payload())
        response = client.post(BASE, json=intern_payload())

        assert response.status_code == 409
        assert response.headers["content-type"] == "application/problem+json"
        problem = response.json()
        assert problem["type"].endswith("/email-already-used")
        assert problem["status"] == 409
        assert problem["instance"] == BASE

    def test_invalid_payload_lists_errors(self, client: TestClient) -> None:
        response = client.post(BASE, json=intern_payload(email="pas-un-email", study_level="x"))

        assert response.status_code == 422
        fields = {tuple(e["location"])[-1] for e in response.json()["errors"]}
        assert fields == {"email", "study_level"}

    def test_unknown_fields_are_rejected(self, client: TestClient) -> None:
        response = client.post(BASE, json=intern_payload(is_admin=True))
        assert response.status_code == 422


class TestReadInternEndpoints:
    def test_get_by_id(self, client: TestClient) -> None:
        created = client.post(BASE, json=intern_payload()).json()

        response = client.get(f"{BASE}/{created['id']}")

        assert response.status_code == 200
        assert response.json() == created

    def test_get_unknown_returns_404(self, client: TestClient) -> None:
        response = client.get(f"{BASE}/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["type"].endswith("/intern-not-found")

    def test_get_with_malformed_id_returns_422(self, client: TestClient) -> None:
        assert client.get(f"{BASE}/pas-un-uuid").status_code == 422

    def test_list_is_paginated(self, client: TestClient) -> None:
        for i in range(3):
            client.post(BASE, json=intern_payload(email=f"s{i}@example.com"))

        body = client.get(BASE, params={"limit": 2}).json()

        assert body["total"] == 3
        assert len(body["items"]) == 2

    def test_limit_above_maximum_is_rejected(self, client: TestClient) -> None:
        assert client.get(BASE, params={"limit": 1000}).status_code == 422


class TestCrossCuttingConcerns:
    def test_request_id_is_generated(self, client: TestClient) -> None:
        response = client.get("/health/live")
        assert len(response.headers["X-Request-ID"]) == 36

    def test_valid_incoming_request_id_is_propagated(self, client: TestClient) -> None:
        response = client.get("/health/live", headers={"X-Request-ID": "trace-12345678"})
        assert response.headers["X-Request-ID"] == "trace-12345678"

    def test_malicious_request_id_is_replaced(self, client: TestClient) -> None:
        response = client.get("/health/live", headers={"X-Request-ID": "x\nfake-log-line"})
        assert response.headers["X-Request-ID"] != "x\nfake-log-line"

    def test_unknown_route_uses_problem_format(self, client: TestClient) -> None:
        response = client.get("/inexistant")
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"

    def test_readiness(self, client: TestClient) -> None:
        assert client.get("/health/ready").json() == {"status": "ok"}
