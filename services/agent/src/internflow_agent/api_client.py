"""Accès à l'API InternFlow avec le jeton de l'utilisateur.

L'agent ne détient aucun droit propre : chaque appel porte le jeton de la personne
qui discute avec lui. Il ne peut donc jamais voir ni faire plus qu'elle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class ApiCallError(Exception):
    """Refus ou erreur de l'API (le détail RFC 9457 est conservé)."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class ApiUnreachableError(Exception):
    """L'API InternFlow ne répond pas (réseau, délai dépassé)."""


@dataclass(frozen=True, slots=True)
class Me:
    user_id: str
    role: str
    intern_id: str | None
    supervisor_id: str | None


JsonObject = dict[str, Any]


class InternFlowApi(Protocol):
    """Port : ce dont l'agent a besoin, indépendamment du transport HTTP."""

    def me(self) -> Me: ...
    def list_internships(self, status: str | None = None) -> list[JsonObject]: ...
    def get_internship(self, internship_id: str) -> JsonObject: ...
    def list_tasks(self, internship_id: str) -> list[JsonObject]: ...
    def list_reports(self, internship_id: str) -> list[JsonObject]: ...
    def get_intern(self, intern_id: str) -> JsonObject: ...
    def get_supervisor(self, supervisor_id: str) -> JsonObject: ...
    def create_task(
        self, internship_id: str, *, title: str, description: str, due_date: str
    ) -> JsonObject: ...
    def search_reports(
        self, question: str, internship_id: str | None = None, limit: int = 5
    ) -> list[JsonObject]: ...


class HttpInternFlowApi:
    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._headers = {"Authorization": f"Bearer {token}"}

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        json: JsonObject | None = None,
    ) -> Any:  # noqa: ANN401 (JSON dynamique, typé par chaque appelant)
        try:
            response = self._client.request(
                method, path, headers=self._headers, params=params, json=json
            )
        except httpx.TransportError as error:
            raise ApiUnreachableError(str(error)) from error
        if response.is_error:
            try:
                detail = str(response.json().get("detail", response.reason_phrase))
            except ValueError:
                detail = response.reason_phrase
            raise ApiCallError(response.status_code, detail)
        return response.json()

    def me(self) -> Me:
        data = self._call("GET", "/api/v1/auth/me")
        return Me(
            user_id=data["user_id"],
            role=data["role"],
            intern_id=data.get("intern_id"),
            supervisor_id=data.get("supervisor_id"),
        )

    def list_internships(self, status: str | None = None) -> list[JsonObject]:
        params: dict[str, str | int] = {"limit": 100}
        if status:
            params["status"] = status
        items: list[JsonObject] = self._call("GET", "/api/v1/internships", params=params)["items"]
        return items

    def get_internship(self, internship_id: str) -> JsonObject:
        data: JsonObject = self._call("GET", f"/api/v1/internships/{internship_id}")
        return data

    def list_tasks(self, internship_id: str) -> list[JsonObject]:
        data: list[JsonObject] = self._call("GET", f"/api/v1/internships/{internship_id}/tasks")
        return data

    def list_reports(self, internship_id: str) -> list[JsonObject]:
        data: list[JsonObject] = self._call("GET", f"/api/v1/internships/{internship_id}/reports")
        return data

    def get_intern(self, intern_id: str) -> JsonObject:
        data: JsonObject = self._call("GET", f"/api/v1/interns/{intern_id}")
        return data

    def get_supervisor(self, supervisor_id: str) -> JsonObject:
        data: JsonObject = self._call("GET", f"/api/v1/supervisors/{supervisor_id}")
        return data

    def create_task(
        self, internship_id: str, *, title: str, description: str, due_date: str
    ) -> JsonObject:
        data: JsonObject = self._call(
            "POST",
            f"/api/v1/internships/{internship_id}/tasks",
            json={"title": title, "description": description, "due_date": due_date},
        )
        return data

    def search_reports(
        self, question: str, internship_id: str | None = None, limit: int = 5
    ) -> list[JsonObject]:
        params: dict[str, str | int] = {"q": question, "limit": limit}
        if internship_id:
            params["internship_id"] = internship_id
        data: list[JsonObject] = self._call("GET", "/api/v1/reports/search", params=params)
        return data
