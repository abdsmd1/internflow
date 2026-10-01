"""Middleware de corrélation : chaque requête reçoit un identifiant unique.

Il est renvoyé dans l'en-tête `X-Request-ID` et ajouté à tous les logs,
ce qui permet de suivre une requête de bout en bout (API → agent → jobs).
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")

logger = structlog.get_logger("internflow.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        # On ne fait pas confiance aveuglément à l'en-tête entrant (injection dans les logs).
        request_id = incoming if _VALID_REQUEST_ID.match(incoming) else str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return response
