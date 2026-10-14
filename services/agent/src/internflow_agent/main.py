"""API HTTP de l'assistant (composition root)."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from http import HTTPStatus
from typing import Annotated, Any, Literal
from uuid import UUID

import httpx
import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, ConfigDict, Field

from internflow_agent import __version__
from internflow_agent.api_client import ApiCallError, ApiUnreachableError, HttpInternFlowApi
from internflow_agent.config import AgentSettings, get_settings
from internflow_agent.llm import build_chat_model, warm_up
from internflow_agent.service import (
    AgentError,
    AgentReply,
    AgentService,
    ApiFactory,
    UnauthenticatedError,
)

logger = structlog.get_logger(__name__)

PROBLEM_BASE = "https://internflow.dev/problems/"
MAX_MESSAGE_LENGTH = 2000


# ---------------------------------------------------------------- DTO


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    thread_id: UUID | None = Field(
        default=None, description="Absent pour une nouvelle conversation."
    )


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool


class PendingTask(BaseModel):
    kind: Literal["create_task"] = "create_task"
    internship_id: str
    internship_subject: str
    title: str
    due_date: str
    description: str


class ChatResponse(BaseModel):
    thread_id: UUID
    reply: str | None = Field(description="Réponse du modèle, absente si une action attend.")
    tools_used: list[str] = Field(description="Outils appelés pendant ce tour (transparence).")
    pending_action: PendingTask | None = Field(
        description="Action proposée qui attend la confirmation de l'utilisateur."
    )

    @classmethod
    def from_reply(cls, reply: AgentReply) -> ChatResponse:
        pending = None
        if reply.pending_action is not None:
            pending = PendingTask(**reply.pending_action.details)
        return cls(
            thread_id=UUID(reply.thread_id),
            reply=reply.reply,
            tools_used=reply.tools_used,
            pending_action=pending,
        )


# ---------------------------------------------------------------- erreurs


def problem(request: Request, status: int, code: str, detail: str, **extra: object) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status == HTTPStatus.UNAUTHORIZED else None
    body = {
        "type": f"{PROBLEM_BASE}{code}",
        "title": "Erreur",
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        **extra,
    }
    return JSONResponse(body, status, media_type="application/problem+json", headers=headers)


def register_errors(app: FastAPI) -> None:
    @app.exception_handler(AgentError)
    async def agent_error(request: Request, exc: AgentError) -> JSONResponse:
        return problem(request, exc.status, exc.code, str(exc))

    @app.exception_handler(ApiCallError)
    async def api_error(request: Request, exc: ApiCallError) -> JSONResponse:
        return problem(request, 502, "api-error", f"L'API a répondu {exc.status} : {exc.detail}")

    @app.exception_handler(ApiUnreachableError)
    async def api_unreachable(request: Request, exc: ApiUnreachableError) -> JSONResponse:
        return problem(request, 502, "api-unreachable", "L'API InternFlow est injoignable.")

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]
        return problem(
            request,
            422,
            "validation-error",
            "La requête contient des données invalides.",
            errors=errors,
        )


# ---------------------------------------------------------------- application

bearer = HTTPBearer(auto_error=False)


def token_from(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> str:
    if credentials is None:
        raise UnauthenticatedError("Jeton d'accès absent.")
    return credentials.credentials


def create_app(
    settings: AgentSettings | None = None,
    *,
    model: BaseChatModel | None = None,
    api_factory: ApiFactory | None = None,
    today: Callable[[], date] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    http = httpx.Client(base_url=settings.api_url, timeout=settings.api_timeout_seconds)

    chat_model = model or build_chat_model(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Configuration effective, visible dès le démarrage (jamais la clé).
        logger.info(
            "agent_config",
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_url=settings.api_url,
        )
        if model is None and settings.llm_warmup:
            # En arrière-plan : le service répond tout de suite, le modèle se charge.
            threading.Thread(target=warm_up, args=(chat_model,), daemon=True).start()
        yield
        http.close()

    def default_today() -> date:
        return datetime.now(UTC).date()

    service = AgentService(
        chat_model,
        api_factory or (lambda token: HttpInternFlowApi(http, token)),
        # Conversations en mémoire : perdues au redémarrage (voir ADR 0011).
        InMemorySaver(),
        max_steps=settings.max_steps,
        today=today or default_today,
    )

    app = FastAPI(
        title="InternFlow Agent",
        version=__version__,
        description="Assistant IA qui agit via l'API InternFlow, avec validation humaine.",
        lifespan=lifespan,
    )
    register_errors(app)

    @app.get("/health/live", tags=["santé"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    responses: dict[int | str, dict[str, Any]] = {
        401: {"description": "Jeton absent, invalide ou expiré (RFC 9457)"},
        503: {"description": "Modèle de langage indisponible (RFC 9457)"},
    }

    @app.post(
        "/api/v1/agent/chat",
        tags=["assistant"],
        summary="Envoyer un message à l'assistant",
        responses=responses,
    )
    def chat(body: ChatRequest, token: Annotated[str, Depends(token_from)]) -> ChatResponse:
        thread_id = str(body.thread_id) if body.thread_id else None
        return ChatResponse.from_reply(service.chat(token, body.message, thread_id))

    @app.post(
        "/api/v1/agent/threads/{thread_id}/decision",
        tags=["assistant"],
        summary="Confirmer ou refuser l'action proposée par l'assistant",
        responses={
            **responses,
            404: {"description": "Conversation introuvable"},
            409: {"description": "Aucune action en attente"},
        },
    )
    def decide(
        thread_id: UUID, body: DecisionRequest, token: Annotated[str, Depends(token_from)]
    ) -> ChatResponse:
        return ChatResponse.from_reply(
            service.decide(token, str(thread_id), approved=body.approved)
        )

    return app
