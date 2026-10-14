"""Doublures de test : un faux modèle scénarisé et une fausse API en mémoire."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from internflow_agent.api_client import ApiCallError, JsonObject, Me


class ScriptedModel(BaseChatModel):
    """Renvoie des réponses écrites à l'avance ; mémorise ce qu'il a reçu."""

    script: list[AIMessage | Exception]
    received: list[list[BaseMessage]] = []  # noqa: RUF012 (champ pydantic, recopié par instance)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(  # type: ignore[override]
        self, tools: Sequence[BaseTool], **kwargs: Any
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received.append(list(messages))
        if not self.script:
            raise AssertionError("Le modèle a été appelé plus de fois que prévu.")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return ChatResult(generations=[ChatGeneration(message=step)])


def call(name: str, **args: Any) -> AIMessage:
    """Le modèle décide d'appeler un outil."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call-{name}"}])


def say(text: str) -> AIMessage:
    return AIMessage(content=text)


def looping(name: str) -> Iterator[AIMessage]:
    while True:
        yield call(name)


INTERNSHIP: JsonObject = {
    "id": "stage-1",
    "intern_id": "int-1",
    "supervisor_id": "sup-1",
    "subject": "Agent IA de suivi",
    "start_date": "2026-09-28",
    "end_date": "2026-12-18",
    "status": "ongoing",
}

ACCOUNTS = {
    "jeton-rh": Me("u-rh", "hr", None, None),
    "jeton-encadrant": Me("u-sup", "supervisor", None, "sup-1"),
    "jeton-autre": Me("u-autre", "supervisor", None, "sup-2"),
}


@dataclass
class FakeApi:
    token: str
    internships: list[JsonObject] = field(default_factory=lambda: [dict(INTERNSHIP)])
    tasks: list[JsonObject] = field(
        default_factory=lambda: [
            {
                "title": "Modéliser la base",
                "due_date": "2026-10-09",
                "status": "todo",
                "is_overdue": True,
            },
            {
                "title": "Écrire les tests",
                "due_date": "2026-11-20",
                "status": "todo",
                "is_overdue": False,
            },
        ]
    )
    reports: list[JsonObject] = field(
        default_factory=lambda: [
            {
                "week": "2026-W41",
                "status": "submitted",
                "accomplishments": "Schéma terminé",
                "difficulties": "",
                "next_steps": "Tests",
            }
        ]
    )
    search_hits: list[JsonObject] = field(default_factory=list)
    searches: list[tuple[str, str | None]] = field(default_factory=list)
    created: list[JsonObject] = field(default_factory=list)
    on_call: Callable[[str], None] | None = None

    def _check(self, name: str) -> None:
        if self.on_call:
            self.on_call(name)

    def me(self) -> Me:
        if self.token not in ACCOUNTS:
            raise ApiCallError(401, "Jeton d'accès absent, invalide ou expiré.")
        return ACCOUNTS[self.token]

    def list_internships(self, status: str | None = None) -> list[JsonObject]:
        self._check("list_internships")
        return [i for i in self.internships if status in (None, i["status"])]

    def get_internship(self, internship_id: str) -> JsonObject:
        self._check("get_internship")
        for internship in self.internships:
            if internship["id"] == internship_id:
                return internship
        raise ApiCallError(404, "Stage introuvable.")

    def list_tasks(self, internship_id: str) -> list[JsonObject]:
        self.get_internship(internship_id)
        return self.tasks

    def list_reports(self, internship_id: str) -> list[JsonObject]:
        self.get_internship(internship_id)
        return self.reports

    def get_intern(self, intern_id: str) -> JsonObject:
        if intern_id != "int-1":
            raise ApiCallError(404, "Stagiaire introuvable.")
        return {"first_name": "Sara", "last_name": "El Amrani"}

    def get_supervisor(self, supervisor_id: str) -> JsonObject:
        return {"first_name": "Karim", "last_name": "Benali"}

    def create_task(
        self, internship_id: str, *, title: str, description: str, due_date: str
    ) -> JsonObject:
        if self.token == "jeton-autre":
            raise ApiCallError(403, "Action réservée à l'encadrant du stage.")
        task = {"title": title, "description": description, "due_date": due_date}
        self.created.append({"internship_id": internship_id, **task})
        return task

    def search_reports(
        self, question: str, internship_id: str | None = None, limit: int = 5
    ) -> list[JsonObject]:
        self._check("search_reports")
        self.searches.append((question, internship_id))
        return self.search_hits[:limit]
