"""Le client HTTP transmet le jeton de l'utilisateur et traduit les erreurs RFC 9457."""

from __future__ import annotations

import json

import httpx
import pytest

from internflow_agent.api_client import ApiCallError, ApiUnreachableError, HttpInternFlowApi


def client_with(handler: httpx.MockTransport) -> HttpInternFlowApi:
    return HttpInternFlowApi(httpx.Client(base_url="http://api", transport=handler), "jeton")


def test_forwards_the_user_token_and_parses_json() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        routes = {
            "/api/v1/auth/me": {
                "user_id": "u",
                "role": "hr",
                "intern_id": None,
                "supervisor_id": None,
            },
            "/api/v1/internships": {"items": [{"id": "s"}], "total": 1},
            "/api/v1/internships/s": {"id": "s"},
            "/api/v1/internships/s/tasks": [{"title": "t"}],
            "/api/v1/internships/s/reports": [],
            "/api/v1/interns/i": {"first_name": "A"},
            "/api/v1/supervisors/p": {"first_name": "B"},
        }
        if request.method == "POST":
            return httpx.Response(201, json=json.loads(request.content))
        return httpx.Response(200, json=routes[request.url.path])

    api = client_with(httpx.MockTransport(handler))
    assert api.me().role == "hr"
    assert api.list_internships("ongoing") == [{"id": "s"}]
    assert api.get_internship("s") == {"id": "s"}
    assert api.list_tasks("s") == [{"title": "t"}]
    assert api.list_reports("s") == []
    assert api.get_intern("i") == {"first_name": "A"}
    assert api.get_supervisor("p") == {"first_name": "B"}
    created = api.create_task("s", title="T", description="", due_date="2026-10-30")
    assert created == {"title": "T", "description": "", "due_date": "2026-10-30"}

    assert {r.headers["Authorization"] for r in seen} == {"Bearer jeton"}
    assert seen[1].url.params["status"] == "ongoing"


def test_problem_details_become_api_errors() -> None:
    api = client_with(
        httpx.MockTransport(
            lambda r: httpx.Response(403, json={"status": 403, "detail": "Action refusée."})
        )
    )
    with pytest.raises(ApiCallError) as error:
        api.get_internship("s")
    assert (error.value.status, error.value.detail) == (403, "Action refusée.")


def test_non_json_errors_are_handled() -> None:
    api = client_with(httpx.MockTransport(lambda r: httpx.Response(502, text="<html>")))
    with pytest.raises(ApiCallError, match="Bad Gateway"):
        api.me()


def test_network_failures_are_reported_as_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refusé", request=request)

    with pytest.raises(ApiUnreachableError):
        client_with(httpx.MockTransport(handler)).me()
