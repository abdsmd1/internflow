"""Erreurs HTTP au format standard RFC 9457 (Problem Details).

Toutes les erreurs ont la même forme pour le client, et aucune trace interne
(stack trace, requête SQL) n'est jamais renvoyée.
"""

from __future__ import annotations

from http import HTTPStatus

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from internflow_api.domain.exceptions import (
    BusinessRuleViolationError,
    DomainError,
    InvalidValueError,
    NotFoundError,
)

PROBLEM_JSON = "application/problem+json"
_PROBLEM_BASE_URI = "https://internflow.dev/problems/"

# Correspondance CATÉGORIE d'erreur métier → statut HTTP.
# Une nouvelle exception métier n'exige aucune modification ici : elle hérite
# de sa catégorie, et son `code` devient le type du problème.
_STATUS_BY_CATEGORY: dict[type[DomainError], HTTPStatus] = {
    NotFoundError: HTTPStatus.NOT_FOUND,
    BusinessRuleViolationError: HTTPStatus.CONFLICT,
    InvalidValueError: HTTPStatus.UNPROCESSABLE_ENTITY,
}

logger = structlog.get_logger(__name__)


def problem(
    request: Request,
    status: HTTPStatus,
    problem_type: str,
    detail: str,
    **extensions: object,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"{_PROBLEM_BASE_URI}{problem_type}",
        "title": status.phrase,
        "status": status.value,
        "detail": detail,
        "instance": request.url.path,
        **extensions,
    }
    return JSONResponse(body, status_code=status.value, media_type=PROBLEM_JSON)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status = next(
            (code for cls, code in _STATUS_BY_CATEGORY.items() if isinstance(exc, cls)),
            HTTPStatus.BAD_REQUEST,
        )
        return problem(request, status, exc.code, str(exc))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {"location": list(err["loc"]), "message": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return problem(
            request,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "validation-error",
            "La requête contient des données invalides.",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = HTTPStatus(exc.status_code)
        return problem(request, status, status.phrase.lower().replace(" ", "-"), str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Le détail complet part dans les logs, jamais dans la réponse.
        logger.exception("unhandled_error", path=request.url.path)
        return problem(
            request,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "internal-error",
            "Une erreur inattendue est survenue.",
        )
