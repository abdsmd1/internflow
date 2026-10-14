"""Cas d'usage de l'assistant : discuter, puis confirmer ou refuser une action proposée."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from http import HTTPStatus
from typing import Any

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import MessagesState
from langgraph.types import Command

from internflow_agent.api_client import ApiCallError, InternFlowApi
from internflow_agent.graph import AgentGraph, build_graph
from internflow_agent.llm import MODEL_UNAVAILABLE_ERRORS
from internflow_agent.tools import build_tools

logger = structlog.get_logger(__name__)


class AgentError(Exception):
    """Erreur métier de l'assistant, traduite en réponse RFC 9457."""

    status = 400
    code = "agent-error"


class UnauthenticatedError(AgentError):
    status = 401
    code = "invalid-token"


class ConversationNotFoundError(AgentError):
    status = 404
    code = "conversation-not-found"


class NoPendingActionError(AgentError):
    status = 409
    code = "no-pending-action"


class ModelUnavailableError(AgentError):
    status = 503
    code = "model-unavailable"


@dataclass(frozen=True, slots=True)
class PendingAction:
    kind: str
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AgentReply:
    thread_id: str
    reply: str | None
    tools_used: list[str] = field(default_factory=list)
    pending_action: PendingAction | None = None


ApiFactory = Callable[[str], InternFlowApi]
GraphInput = MessagesState | Command[Any]

TOO_LONG = (
    "Je n'ai pas réussi à aboutir en un nombre raisonnable d'étapes. "
    "Pouvez-vous reformuler la question plus précisément ?"
)


class AgentService:
    def __init__(
        self,
        model: BaseChatModel,
        api_factory: ApiFactory,
        checkpointer: BaseCheckpointSaver[str],
        *,
        max_steps: int,
        today: Callable[[], date],
    ) -> None:
        self._model = model
        self._api_factory = api_factory
        self._checkpointer = checkpointer
        self._max_steps = max_steps
        self._today = today
        # Une conversation appartient à l'utilisateur qui l'a ouverte, et à lui seul.
        self._owners: dict[str, str] = {}
        self._lock = threading.Lock()

    def chat(self, token: str, message: str, thread_id: str | None) -> AgentReply:
        api, user_id, role = self._authenticate(token)
        if thread_id is None:
            thread_id = str(uuid.uuid4())
            with self._lock:
                self._owners[thread_id] = user_id
        else:
            self._ensure_owner(thread_id, user_id)
        return self._run(api, role, thread_id, MessagesState(messages=[HumanMessage(message)]))

    def decide(self, token: str, thread_id: str, *, approved: bool) -> AgentReply:
        api, user_id, role = self._authenticate(token)
        self._ensure_owner(thread_id, user_id)
        graph = self._graph(api, role)
        if not graph.get_state(self._config(thread_id)).interrupts:
            raise NoPendingActionError("Aucune action n'attend de confirmation.")
        logger.info("agent_decision", approved=approved)
        return self._run(api, role, thread_id, Command(resume={"approved": approved}))

    # ------------------------------------------------------------------ interne

    def _authenticate(self, token: str) -> tuple[InternFlowApi, str, str]:
        api = self._api_factory(token)
        try:
            me = api.me()  # l'API reste seule juge de la validité du jeton
        except ApiCallError as error:
            if error.status == HTTPStatus.UNAUTHORIZED:
                raise UnauthenticatedError(error.detail) from error
            raise
        return api, me.user_id, me.role

    def _ensure_owner(self, thread_id: str, user_id: str) -> None:
        with self._lock:
            owner = self._owners.get(thread_id)
        if owner != user_id:  # même message que si elle n'existait pas
            raise ConversationNotFoundError("Conversation introuvable.")

    def _config(self, thread_id: str) -> RunnableConfig:
        return RunnableConfig(
            configurable={"thread_id": thread_id},
            recursion_limit=2 * self._max_steps + 1,
        )

    def _graph(self, api: InternFlowApi, role: str) -> AgentGraph:
        return build_graph(
            self._model, build_tools(api), self._checkpointer, role=role, today=self._today()
        )

    def _run(
        self, api: InternFlowApi, role: str, thread_id: str, payload: GraphInput
    ) -> AgentReply:
        graph = self._graph(api, role)
        config = self._config(thread_id)
        before = len(graph.get_state(config).values.get("messages", []))
        try:
            result = graph.invoke(payload, config, version="v2")
        except GraphRecursionError:
            return AgentReply(thread_id=thread_id, reply=TOO_LONG)
        except MODEL_UNAVAILABLE_ERRORS as error:
            logger.warning("model_unavailable", error=type(error).__name__)
            raise ModelUnavailableError(
                "Le modèle de langage ne répond pas : vérifiez qu'Ollama est démarré "
                "et que le modèle est téléchargé."
            ) from error

        new_messages = result.value["messages"][before:]
        tools_used = [m.name for m in new_messages if isinstance(m, ToolMessage) and m.name]
        logger.info("agent_turn", tools=tools_used)

        if result.interrupts:
            details = dict(result.interrupts[0].value)
            return AgentReply(
                thread_id=thread_id,
                reply=None,
                tools_used=tools_used,
                pending_action=PendingAction(kind=str(details.pop("kind")), details=details),
            )

        final = next(
            (m for m in reversed(new_messages) if isinstance(m, AIMessage) and m.content), None
        )
        return AgentReply(
            thread_id=thread_id,
            reply=final.text if final else None,
            tools_used=tools_used,
        )
